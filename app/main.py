import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "app.db"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
      line = raw_line.strip()
      if not line or line.startswith("#") or "=" not in line:
          continue
      key, value = line.split("=", 1)
      os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env(ROOT / ".env")

PORT = int(os.getenv("PORT", "8000"))
APP_URL = os.getenv("APP_URL", f"http://localhost:{PORT}")
SESSION_SECRET = os.getenv("SESSION_SECRET", "local-development-secret")

PACKAGES = {
    "outreach": {
        "key": "outreach",
        "name": "Guest Outreach",
        "price": 149,
        "description": "SMS and email review requests to guests.",
        "features": ["SMS review requests", "Email review requests", "Guest feedback dashboard", "Delivery logs"],
        "stripe_env": "STRIPE_PRICE_ID_OUTREACH",
    },
    "reputation": {
        "key": "reputation",
        "name": "Reputation Management",
        "price": 249,
        "description": "SMS/email outreach plus replying to online reviews.",
        "features": ["Everything in Guest Outreach", "Online review reply management", "Follow-up notes", "Reputation workflow"],
        "stripe_env": "STRIPE_PRICE_ID_REPUTATION",
    },
    "social": {
        "key": "social",
        "name": "Social Management",
        "price": 349,
        "description": "Outreach, review replies, and social media post management.",
        "features": ["Everything in Reputation Management", "Facebook post management", "Social content coordination", "Premium service workflow"],
        "stripe_env": "STRIPE_PRICE_ID_SOCIAL",
    },
}

app = FastAPI(title="Truvora Python Platform")
templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")

serializer = URLSafeSerializer(SESSION_SECRET, salt="Truvora-session")
subscribers: dict[int, set[asyncio.Queue]] = {}


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
async def auth_page(request: Request):
    if current_user(request):
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/register")
async def register(
    hotel_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    email = email.strip().lower()
    hotel_name = hotel_name.strip()
    if not hotel_name or "@" not in email or len(password) < 8:
        raise HTTPException(400, "Hotel name, valid email, and 8+ character password are required.")

    with db() as conn:
        existing = conn.execute("select id from users where email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(409, "An account already exists for this email.")

        hotel_id = insert(
            conn,
            "hotels",
            {
                "name": hotel_name,
                "google_link": "https://www.google.com/search?q=hotel+reviews",
                "sms_template": "Hi {guest}, thanks for staying at {hotel}. Share feedback here: {link}",
                "email_template": "Hello {guest},\n\nThank you for staying at {hotel}. Share feedback here: {link}",
                "plan": "trial",
                "payment_status": "trial",
                "package_key": None,
                "trial_ends_at": trial_end(),
                "cancellation_requested_at": None,
                "cancellation_effective_at": None,
                "subscription_renews_at": None,
                "pending_package_key": None,
                "pending_package_effective_at": None,
                "created_at": now(),
            },
        )
        user_id = insert(
            conn,
            "users",
            {
                "email": email,
                "password_hash": hash_password(password),
                "hotel_id": hotel_id,
                "created_at": now(),
            },
        )

    response = RedirectResponse("/app", status_code=303)
    set_session(response, user_id)
    return response


@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    with db() as conn:
        user = conn.execute("select * from users where email = ?", (email.strip().lower(),)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")

    response = RedirectResponse("/app", status_code=303)
    set_session(response, user["id"])
    return response


@app.post("/api/auth/register")
async def api_register(request: Request):
    body = await request.json()
    hotel_name = clean(body.get("hotelName"))
    email = clean(body.get("email")).lower()
    password = str(body.get("password") or "")
    if not hotel_name or "@" not in email or len(password) < 8:
        raise HTTPException(400, "Hotel name, valid email, and 8+ character password are required.")

    with db() as conn:
        if conn.execute("select id from users where email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account already exists for this email.")
        hotel_id = create_hotel(conn, hotel_name)
        user_id = insert(
            conn,
            "users",
            {
                "email": email,
                "password_hash": hash_password(password),
                "hotel_id": hotel_id,
                "created_at": now(),
            },
        )

    response = JSONResponse({"ok": True})
    set_session(response, user_id)
    return response


@app.post("/api/auth/login")
async def api_login(request: Request):
    body = await request.json()
    email = clean(body.get("email")).lower()
    password = str(body.get("password") or "")
    with db() as conn:
        user = conn.execute("select * from users where email = ?", (email,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    response = JSONResponse({"ok": True})
    set_session(response, user["id"])
    return response


@app.post("/api/auth/forgot-password")
async def api_forgot_password(request: Request):
    body = await request.json()
    email = clean(body.get("email")).lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address.")

    reset_url = None
    delivery = None
    with db() as conn:
        user = conn.execute("select * from users where email = ?", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            conn.execute("update password_resets set used_at = ? where user_id = ? and used_at is null", (now(), user["id"]))
            insert(
                conn,
                "password_resets",
                {
                    "user_id": user["id"],
                    "token_hash": token_hash,
                    "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                    "used_at": None,
                    "created_at": now(),
                },
            )
            reset_url = f"{APP_URL}/reset-password?t={token}"
            delivery = await send_email(
                email,
                "Reset your Truvora password",
                f"Use this link within 30 minutes to reset your password:\n\n{reset_url}",
            )

    payload = {"ok": True, "message": "If an account exists for that email, a reset link has been prepared."}
    if reset_url and delivery and delivery["provider"] == "local":
        payload["message"] = "Email delivery is not configured, so use this local reset link:"
        payload["resetUrl"] = reset_url
    return payload


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, t: str):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": t})


@app.post("/api/auth/reset-password")
async def api_reset_password(request: Request):
    body = await request.json()
    token = str(body.get("token") or "")
    password = str(body.get("password") or "")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with db() as conn:
        reset = conn.execute(
            """
            select * from password_resets
            where token_hash = ? and used_at is null
            order by id desc
            limit 1
            """,
            (token_hash,),
        ).fetchone()
        if not reset or parse_dt(reset["expires_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(400, "This reset link is invalid or has expired.")
        conn.execute("update users set password_hash = ? where id = ?", (hash_password(password), reset["user_id"]))
        conn.execute("update password_resets set used_at = ? where id = ?", (now(), reset["id"]))
    return {"ok": True, "message": "Password updated. You can now log in."}


@app.post("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("sid", path="/")
    return response


@app.get("/app", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = require_user(request)
    return templates.TemplateResponse("app.html", {"request": request, "user": user})


@app.get("/guest", response_class=HTMLResponse)
async def guest_page(request: Request, t: str):
    with db() as conn:
        guest = public_guest_context(conn, t)
    if not guest:
        raise HTTPException(404, "Feedback link not found.")
    return templates.TemplateResponse("guest.html", {"request": request, "guest": guest, "token": t})


@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    require_user(request)
    return templates.TemplateResponse("billing.html", {"request": request})


@app.get("/api/me")
async def api_me(request: Request):
    user = require_user(request)
    return user_context(user)


@app.put("/api/settings")
async def api_settings(request: Request):
    user = require_user(request)
    body = await request.json()
    with db() as conn:
        conn.execute(
            """
            update hotels
            set name = ?, google_link = ?, sms_template = ?, email_template = ?
            where id = ?
            """,
            (
                clean(body.get("name")),
                clean(body.get("googleLink")),
                clean(body.get("smsTemplate")),
                clean(body.get("emailTemplate")),
                user["hotel_id"],
            ),
        )
        conn.commit()
        payload = user_context(user)
    await broadcast(user["hotel_id"], "settings", payload)
    return payload


@app.get("/api/requests")
async def api_requests(request: Request):
    user = require_user(request)
    with db() as conn:
        return list_requests(conn, user["hotel_id"])


@app.post("/api/requests")
async def api_create_request(request: Request):
    user = require_user(request)
    require_platform_access(user)
    body = await request.json()
    required = ["guestName", "phone", "email", "stayDate"]
    if any(not clean(body.get(field)) for field in required):
        raise HTTPException(400, "Guest name, phone, email, and stay date are required.")

    token = secrets.token_urlsafe(24)
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
        request_id = insert(
            conn,
            "requests",
            {
                "hotel_id": user["hotel_id"],
                "guest_name": clean(body["guestName"]),
                "phone": clean(body["phone"]),
                "email": clean(body["email"]).lower(),
                "stay_date": clean(body["stayDate"]),
                "token": token,
                "status": "sent",
                "notes": "",
                "sent_at": now(),
                "opened_at": None,
                "responded_at": None,
            },
        )
        created = conn.execute("select * from requests where id = ?", (request_id,)).fetchone()
        delivery = await send_review_request(conn, hotel, created)
        requests_payload = list_requests(conn, user["hotel_id"])
        deliveries_payload = list_deliveries(conn, user["hotel_id"])

    await broadcast(user["hotel_id"], "requests", requests_payload)
    await broadcast(user["hotel_id"], "deliveries", deliveries_payload)
    return {**shape_request(created, None), "feedbackUrl": feedback_url(token), "delivery": delivery}


@app.put("/api/requests/{request_id}/notes")
async def api_update_notes(request_id: int, request: Request):
    user = require_user(request)
    require_platform_access(user)
    body = await request.json()
    with db() as conn:
        conn.execute(
            "update requests set notes = ? where id = ? and hotel_id = ?",
            (str(body.get("notes", "")), request_id, user["hotel_id"]),
        )
        payload = list_requests(conn, user["hotel_id"])
    await broadcast(user["hotel_id"], "requests", payload)
    return {"ok": True}


@app.get("/api/deliveries")
async def api_deliveries(request: Request):
    user = require_user(request)
    with db() as conn:
        return list_deliveries(conn, user["hotel_id"])


@app.get("/api/realtime")
async def api_realtime(request: Request):
    user = require_user(request)
    queue: asyncio.Queue = asyncio.Queue()
    hotel_id = user["hotel_id"]
    subscribers.setdefault(hotel_id, set()).add(queue)

    async def events():
        try:
            yield sse("hello", {"ok": True})
            while True:
                event, payload = await queue.get()
                yield sse(event, payload)
        finally:
            subscribers.get(hotel_id, set()).discard(queue)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/public/request/{token}")
async def api_public_request(token: str):
    with db() as conn:
        request = conn.execute("select * from requests where token = ?", (token,)).fetchone()
        if not request:
            raise HTTPException(404, "Feedback link not found.")
        hotel = get_hotel(conn, request["hotel_id"])
        if not hotel_has_access(hotel):
            raise HTTPException(402, "This hotel's trial has ended. Feedback links reactivate after payment.")
        if request["status"] == "sent":
            conn.execute(
                "update requests set status = ?, opened_at = ? where id = ?",
                ("opened", now(), request["id"]),
            )
            await broadcast(request["hotel_id"], "requests", list_requests(conn, request["hotel_id"]))
        return {
            "hotelName": hotel["name"],
            "guestName": request["guest_name"],
            "stayDate": request["stay_date"],
            "googleLink": hotel["google_link"],
        }


@app.post("/api/public/feedback/{token}")
async def api_public_feedback(token: str, request: Request):
    body = await request.json()
    rating = int(body.get("rating", 0))
    comments = clean(body.get("comments"))
    if rating < 1 or rating > 5:
        raise HTTPException(400, "Rating must be between 1 and 5.")

    with db() as conn:
        guest_request = conn.execute("select * from requests where token = ?", (token,)).fetchone()
        if not guest_request:
            raise HTTPException(404, "Feedback link not found.")
        hotel = get_hotel(conn, guest_request["hotel_id"])
        if not hotel_has_access(hotel):
            raise HTTPException(402, "This hotel's trial has ended. Feedback links reactivate after payment.")

        existing = conn.execute("select id from feedback where request_id = ?", (guest_request["id"],)).fetchone()
        if existing:
            conn.execute(
                "update feedback set rating = ?, comments = ?, updated_at = ? where id = ?",
                (rating, comments, now(), existing["id"]),
            )
        else:
            insert(
                conn,
                "feedback",
                {
                    "request_id": guest_request["id"],
                    "hotel_id": guest_request["hotel_id"],
                    "rating": rating,
                    "comments": comments,
                    "created_at": now(),
                    "updated_at": now(),
                },
            )
        conn.execute(
            "update requests set status = ?, responded_at = coalesce(responded_at, ?) where id = ?",
            ("responded", now(), guest_request["id"]),
        )
        payload = list_requests(conn, guest_request["hotel_id"])

    await broadcast(guest_request["hotel_id"], "requests", payload)
    return {"ok": True}


@app.post("/api/payments/checkout")
async def api_checkout(request: Request):
    user = require_user(request)
    body = await request.json()
    package_key = package_from_body(body)
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
        if hotel["payment_status"] in {"active", "cancel_pending"}:
            raise HTTPException(400, "Package changes for active accounts are scheduled for the next renewal date.")
    stripe_price_id = stripe_price_for_package(package_key)
    if not os.getenv("STRIPE_SECRET_KEY") or not stripe_price_id:
        return {"mode": "local", "checkoutUrl": f"/billing?package={package_key}"}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(os.getenv("STRIPE_SECRET_KEY"), ""),
            data={
                "mode": "subscription",
                "line_items[0][price]": stripe_price_id,
                "line_items[0][quantity]": "1",
                "success_url": f"{APP_URL}/app?paid=success",
                "cancel_url": f"{APP_URL}/billing?paid=cancelled",
                "client_reference_id": str(user["hotel_id"]),
                "customer_email": user["email"],
                "metadata[hotel_id]": str(user["hotel_id"]),
                "metadata[package_key]": package_key,
            },
        )
    payload = response.json()
    if response.status_code >= 400:
        raise HTTPException(502, payload.get("error", {}).get("message", "Stripe checkout failed."))
    return {"mode": "stripe", "checkoutUrl": payload["url"]}


@app.post("/api/payments/simulate")
async def api_simulate_payment(request: Request):
    user = require_user(request)
    body = await request.json()
    package_key = package_from_body(body)
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
        if hotel["payment_status"] in {"active", "cancel_pending"}:
            raise HTTPException(400, "Package changes for active accounts are scheduled for the next renewal date.")
        activate_hotel(conn, user["hotel_id"], package_key, "local", None)
        conn.commit()
        payload = user_context(user)
    await broadcast(user["hotel_id"], "billing", payload)
    return payload


@app.post("/api/payments/cancel")
async def api_request_cancellation(request: Request):
    user = require_user(request)
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
        if hotel["payment_status"] not in {"active", "cancel_pending"}:
            raise HTTPException(400, "Only active paid packages can be cancelled.")
        if hotel["payment_status"] != "cancel_pending":
            requested_at = now()
            effective_at = notice_period_end(requested_at)
            conn.execute(
                """
                update hotels
                set payment_status = ?, cancellation_requested_at = ?, cancellation_effective_at = ?
                where id = ?
                """,
                ("cancel_pending", requested_at, effective_at, user["hotel_id"]),
            )
            insert(
                conn,
                "payments",
                {
                    "hotel_id": user["hotel_id"],
                    "provider": "platform",
                    "status": "cancellation_requested",
                    "checkout_session_id": None,
                    "amount": None,
                    "currency": "usd",
                    "created_at": requested_at,
                },
            )
        conn.commit()
        payload = user_context(user)
    await broadcast(user["hotel_id"], "billing", payload)
    return payload


@app.post("/api/payments/package-change")
async def api_schedule_package_change(request: Request):
    user = require_user(request)
    body = await request.json()
    package_key = package_from_body(body)
    keep_subscription_active = bool((body or {}).get("keepSubscriptionActive"))
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
        if hotel["payment_status"] not in {"active", "cancel_pending"}:
            raise HTTPException(400, "Choose a package to activate your account first.")
        if hotel["package_key"] == package_key:
            raise HTTPException(400, "This package is already active.")
        effective_at = hotel["subscription_renews_at"] or next_renewal_date()
        payment_status = "active" if keep_subscription_active and hotel["payment_status"] == "cancel_pending" else hotel["payment_status"]
        cancellation_requested_at = None if keep_subscription_active and hotel["payment_status"] == "cancel_pending" else hotel["cancellation_requested_at"]
        cancellation_effective_at = None if keep_subscription_active and hotel["payment_status"] == "cancel_pending" else hotel["cancellation_effective_at"]
        conn.execute(
            """
            update hotels
            set payment_status = ?, pending_package_key = ?, pending_package_effective_at = ?,
                cancellation_requested_at = ?, cancellation_effective_at = ?
            where id = ?
            """,
            (payment_status, package_key, effective_at, cancellation_requested_at, cancellation_effective_at, user["hotel_id"]),
        )
        insert(
            conn,
            "payments",
            {
                "hotel_id": user["hotel_id"],
                "provider": "platform",
                "status": "package_change_scheduled_active" if keep_subscription_active and hotel["payment_status"] == "cancel_pending" else "package_change_scheduled",
                "checkout_session_id": None,
                "amount": PACKAGES[package_key]["price"] * 100,
                "currency": "usd",
                "created_at": now(),
            },
        )
        conn.commit()
        payload = user_context(user)
    await broadcast(user["hotel_id"], "billing", payload)
    return payload


@app.post("/api/payments/webhook")
async def api_stripe_webhook(request: Request):
    raw = await request.body()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if secret and not verify_stripe_signature(raw, request.headers.get("stripe-signature", ""), secret):
        raise HTTPException(400, "Invalid Stripe signature.")

    event = json.loads(raw.decode("utf-8"))
    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        hotel_id = int(session.get("client_reference_id") or session.get("metadata", {}).get("hotel_id"))
        package_key = package_from_body(session.get("metadata", {}))
        with db() as conn:
            activate_hotel(conn, hotel_id, package_key, "stripe", session.get("id"))
            conn.commit()
            user = conn.execute("select * from users where hotel_id = ?", (hotel_id,)).fetchone()
            payload = user_context(user) if user else None
        if payload:
            await broadcast(hotel_id, "billing", payload)
    return {"received": True}


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            create table if not exists hotels (
              id integer primary key autoincrement,
              name text not null,
              google_link text not null,
              sms_template text not null,
              email_template text not null,
              plan text not null,
              payment_status text not null,
              package_key text,
              trial_ends_at text,
              cancellation_requested_at text,
              cancellation_effective_at text,
              subscription_renews_at text,
              pending_package_key text,
              pending_package_effective_at text,
              created_at text not null
            );
            create table if not exists users (
              id integer primary key autoincrement,
              email text not null unique,
              password_hash text not null,
              hotel_id integer not null references hotels(id),
              created_at text not null
            );
            create table if not exists requests (
              id integer primary key autoincrement,
              hotel_id integer not null references hotels(id),
              guest_name text not null,
              phone text not null,
              email text not null,
              stay_date text not null,
              token text not null unique,
              status text not null,
              notes text not null,
              sent_at text not null,
              opened_at text,
              responded_at text
            );
            create table if not exists feedback (
              id integer primary key autoincrement,
              request_id integer not null unique references requests(id),
              hotel_id integer not null references hotels(id),
              rating integer not null,
              comments text not null,
              created_at text not null,
              updated_at text not null
            );
            create table if not exists deliveries (
              id integer primary key autoincrement,
              hotel_id integer not null references hotels(id),
              request_id integer not null references requests(id),
              provider text not null,
              channel text not null,
              status text not null,
              message text not null,
              created_at text not null
            );
            create table if not exists payments (
              id integer primary key autoincrement,
              hotel_id integer not null references hotels(id),
              provider text not null,
              status text not null,
              checkout_session_id text,
              amount integer,
              currency text,
              created_at text not null
            );
            create table if not exists password_resets (
              id integer primary key autoincrement,
              user_id integer not null references users(id),
              token_hash text not null unique,
              expires_at text not null,
              used_at text,
              created_at text not null
            );
            """
        )
        ensure_column(conn, "hotels", "package_key", "text")
        ensure_column(conn, "hotels", "trial_ends_at", "text")
        ensure_column(conn, "hotels", "cancellation_requested_at", "text")
        ensure_column(conn, "hotels", "cancellation_effective_at", "text")
        ensure_column(conn, "hotels", "subscription_renews_at", "text")
        ensure_column(conn, "hotels", "pending_package_key", "text")
        ensure_column(conn, "hotels", "pending_package_effective_at", "text")
        rows = conn.execute("select id, created_at, trial_ends_at from hotels").fetchall()
        for row in rows:
            if not row["trial_ends_at"]:
                conn.execute("update hotels set trial_ends_at = ? where id = ?", (trial_end(row["created_at"]), row["id"]))
        renewal_rows = conn.execute(
            """
            select id from hotels
            where payment_status in ('active', 'cancel_pending')
              and (subscription_renews_at is null or subscription_renews_at = '')
            """
        ).fetchall()
        for row in renewal_rows:
            conn.execute("update hotels set subscription_renews_at = ? where id = ?", (next_renewal_date(), row["id"]))


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def insert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(values.keys())
    placeholders = ", ".join("?" for _ in values)
    cursor = conn.execute(f"insert into {table} ({columns}) values ({placeholders})", tuple(values.values()))
    return int(cursor.lastrowid)


def create_hotel(conn: sqlite3.Connection, hotel_name: str) -> int:
    return insert(
        conn,
        "hotels",
        {
            "name": hotel_name,
            "google_link": "https://www.google.com/search?q=hotel+reviews",
            "sms_template": "Hi {guest}, thanks for staying at {hotel}. Share feedback here: {link}",
            "email_template": "Hello {guest},\n\nThank you for staying at {hotel}. Share feedback here: {link}",
            "plan": "trial",
            "payment_status": "trial",
            "package_key": None,
            "trial_ends_at": trial_end(),
            "cancellation_requested_at": None,
            "cancellation_effective_at": None,
            "subscription_renews_at": None,
            "pending_package_key": None,
            "pending_package_effective_at": None,
            "created_at": now(),
        },
    )


def current_user(request: Request):
    token = request.cookies.get("sid")
    if not token:
        return None
    try:
        user_id = serializer.loads(token).get("user_id")
    except BadSignature:
        return None
    with db() as conn:
        return conn.execute("select * from users where id = ?", (user_id,)).fetchone()


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required.")
    return user


def set_session(response: Response, user_id: int) -> None:
    response.set_cookie("sid", serializer.dumps({"user_id": user_id}), httponly=True, samesite="lax", path="/")


def user_context(user) -> dict[str, Any]:
    with db() as conn:
        apply_scheduled_package_change(conn, user["hotel_id"])
        hotel = get_hotel(conn, user["hotel_id"])
    access = hotel_access_status(hotel)
    return {
        "user": {"id": user["id"], "email": user["email"]},
        "hotel": {
            "id": hotel["id"],
            "name": hotel["name"],
            "googleLink": hotel["google_link"],
            "smsTemplate": hotel["sms_template"],
            "emailTemplate": hotel["email_template"],
            "plan": hotel["plan"],
            "paymentStatus": hotel["payment_status"],
            "packageKey": hotel["package_key"],
            "trialEndsAt": hotel["trial_ends_at"],
            "cancellationRequestedAt": hotel["cancellation_requested_at"],
            "cancellationEffectiveAt": hotel["cancellation_effective_at"],
            "subscriptionRenewsAt": hotel["subscription_renews_at"],
            "pendingPackageKey": hotel["pending_package_key"],
            "pendingPackageEffectiveAt": hotel["pending_package_effective_at"],
            "accessActive": access["active"],
            "accessReason": access["reason"],
            "trialDaysRemaining": access["trialDaysRemaining"],
        },
        "packages": list(PACKAGES.values()),
    }


def get_hotel(conn: sqlite3.Connection, hotel_id: int):
    return conn.execute("select * from hotels where id = ?", (hotel_id,)).fetchone()


def list_requests(conn: sqlite3.Connection, hotel_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select r.*, f.rating, f.comments
        from requests r
        left join feedback f on f.request_id = r.id
        where r.hotel_id = ?
        order by r.id desc
        """,
        (hotel_id,),
    ).fetchall()
    return [shape_request(row, row) for row in rows]


def shape_request(request, feedback) -> dict[str, Any]:
    return {
        "id": request["id"],
        "guestName": request["guest_name"],
        "phone": request["phone"],
        "email": request["email"],
        "stayDate": request["stay_date"],
        "status": request["status"],
        "rating": feedback["rating"] if feedback and "rating" in feedback.keys() else None,
        "comments": feedback["comments"] if feedback and "comments" in feedback.keys() and feedback["comments"] else "",
        "notes": request["notes"],
        "sentAt": request["sent_at"],
        "openedAt": request["opened_at"],
        "respondedAt": request["responded_at"],
        "feedbackUrl": feedback_url(request["token"]),
    }


def list_deliveries(conn: sqlite3.Connection, hotel_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select d.*, r.guest_name, r.email, r.phone
        from deliveries d
        left join requests r on r.id = d.request_id
        where d.hotel_id = ?
        order by d.id desc
        """,
        (hotel_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "requestId": row["request_id"],
            "guestName": row["guest_name"] or "Unknown guest",
            "guestEmail": row["email"] or "",
            "guestPhone": row["phone"] or "",
            "provider": row["provider"],
            "channel": row["channel"],
            "status": row["status"],
            "message": row["message"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def public_guest_context(conn: sqlite3.Connection, token: str):
    row = conn.execute(
        """
        select r.*, h.name as hotel_name, h.google_link
        from requests r
        join hotels h on h.id = r.hotel_id
        where r.token = ?
        """,
        (token,),
    ).fetchone()
    if not row:
        return None
    return {
        "hotelName": row["hotel_name"],
        "guestName": row["guest_name"],
        "stayDate": row["stay_date"],
        "googleLink": row["google_link"],
    }


async def send_review_request(conn: sqlite3.Connection, hotel, request) -> dict[str, Any]:
    sms_body = render_template(hotel["sms_template"], hotel, request)
    email_body = render_template(hotel["email_template"], hotel, request)
    sms = await send_sms(request["phone"], sms_body)
    email = await send_email(request["email"], f"How was your stay at {hotel['name']}?", email_body)
    for result in [sms, email]:
        insert(
            conn,
            "deliveries",
            {
                "hotel_id": hotel["id"],
                "request_id": request["id"],
                "provider": result["provider"],
                "channel": result["channel"],
                "status": result["status"],
                "message": result["message"],
                "created_at": now(),
            },
        )
    return {"feedbackUrl": feedback_url(request["token"]), "sms": sms, "email": email}


async def send_sms(to: str, body: str) -> dict[str, str]:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_FROM_PHONE")
    if not sid or not token or not from_phone:
        return {"channel": "sms", "provider": "local", "status": "recorded", "message": body}

    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            headers={"Authorization": f"Basic {auth}"},
            data={"To": to, "From": from_phone, "Body": body},
        )
    return {"channel": "sms", "provider": "twilio", "status": "sent" if response.is_success else "failed", "message": body}


async def send_email(to: str, subject: str, body: str) -> dict[str, str]:
    if not os.getenv("BREVO_SMTP_USER") or not os.getenv("BREVO_SMTP_PASS") or not os.getenv("BREVO_FROM_EMAIL"):
        return {"channel": "email", "provider": "local", "status": "recorded", "message": body}

    def send_blocking():
        message = EmailMessage()
        sender_name = os.getenv("BREVO_FROM_NAME", "Truvora")
        message["From"] = f"{sender_name} <{os.getenv('BREVO_FROM_EMAIL')}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com"), int(os.getenv("BREVO_SMTP_PORT", "587"))) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("BREVO_SMTP_USER"), os.getenv("BREVO_SMTP_PASS"))
            smtp.send_message(message)

    try:
        await asyncio.to_thread(send_blocking)
        return {"channel": "email", "provider": "brevo", "status": "sent", "message": body}
    except Exception as exc:
        return {"channel": "email", "provider": "brevo", "status": "failed", "message": f"{exc}\n\n{body}"}


def render_template(template: str, hotel, request) -> str:
    return (
        template.replace("{guest}", request["guest_name"])
        .replace("{hotel}", hotel["name"])
        .replace("{link}", feedback_url(request["token"]))
    )


def feedback_url(token: str) -> str:
    return f"{APP_URL}/guest?t={token}"


def activate_hotel(conn: sqlite3.Connection, hotel_id: int, package_key: str, provider: str, checkout_session_id: str | None) -> None:
    package = PACKAGES[package_key]
    conn.execute(
        """
        update hotels
        set plan = ?, payment_status = ?, package_key = ?,
            subscription_renews_at = ?,
            pending_package_key = null, pending_package_effective_at = null,
            cancellation_requested_at = null, cancellation_effective_at = null
        where id = ?
        """,
        (package_key, "active", package_key, next_renewal_date(), hotel_id),
    )
    insert(
        conn,
        "payments",
        {
            "hotel_id": hotel_id,
            "provider": provider,
            "status": "paid",
            "checkout_session_id": checkout_session_id,
            "amount": package["price"] * 100,
            "currency": "usd",
            "created_at": now(),
        },
    )


async def broadcast(hotel_id: int, event: str, payload: Any) -> None:
    for queue in subscribers.get(hotel_id, set()).copy():
        await queue.put((event, payload))


def sse(event: str, payload: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def verify_stripe_signature(raw: bytes, header: str, secret: str) -> bool:
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    signed_payload = f"{timestamp}.{raw.decode('utf-8')}".encode()
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
    return f"{salt}:{digest}"


def verify_password(password: str, saved_hash: str) -> bool:
    try:
        salt, expected = saved_hash.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(expected, digest)


def clean(value: Any) -> str:
    return str(value or "").strip()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trial_end(created_at: str | None = None) -> str:
    base = parse_dt(created_at) if created_at else datetime.now(timezone.utc)
    return (base + timedelta(days=7)).isoformat()


def notice_period_end(requested_at: str | None = None) -> str:
    base = parse_dt(requested_at) if requested_at else datetime.now(timezone.utc)
    return (base + timedelta(days=60)).isoformat()


def next_renewal_date(base_date: str | None = None) -> str:
    base = parse_dt(base_date) if base_date else datetime.now(timezone.utc)
    return (base + timedelta(days=30)).isoformat()


def apply_scheduled_package_change(conn: sqlite3.Connection, hotel_id: int) -> None:
    hotel = get_hotel(conn, hotel_id)
    if not hotel or not hotel["pending_package_key"] or not hotel["pending_package_effective_at"]:
        return
    if parse_dt(hotel["pending_package_effective_at"]) > datetime.now(timezone.utc):
        return
    package_key = hotel["pending_package_key"]
    conn.execute(
        """
        update hotels
        set plan = ?, package_key = ?, pending_package_key = null,
            pending_package_effective_at = null, subscription_renews_at = ?
        where id = ?
        """,
        (package_key, package_key, next_renewal_date(), hotel_id),
    )


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def hotel_access_status(hotel) -> dict[str, Any]:
    if hotel["payment_status"] == "active":
        return {"active": True, "reason": "paid", "trialDaysRemaining": 0}
    if hotel["payment_status"] == "cancel_pending":
        effective_at = parse_dt(hotel["cancellation_effective_at"])
        if effective_at > datetime.now(timezone.utc):
            return {"active": True, "reason": "cancel_pending", "trialDaysRemaining": 0}
        return {"active": False, "reason": "cancelled", "trialDaysRemaining": 0}
    trial_ends_at = parse_dt(hotel["trial_ends_at"])
    remaining = trial_ends_at - datetime.now(timezone.utc)
    if remaining.total_seconds() > 0:
        days = max(1, int((remaining.total_seconds() + 86399) // 86400))
        return {"active": True, "reason": "trial", "trialDaysRemaining": days}
    return {"active": False, "reason": "trial_expired", "trialDaysRemaining": 0}


def hotel_has_access(hotel) -> bool:
    return hotel_access_status(hotel)["active"]


def require_platform_access(user) -> None:
    with db() as conn:
        hotel = get_hotel(conn, user["hotel_id"])
    if not hotel_has_access(hotel):
        raise HTTPException(402, "Your 7-day trial has ended. Please choose a package to continue using the platform.")


def package_from_body(body: Any) -> str:
    key = clean((body or {}).get("packageKey") or (body or {}).get("package_key") or "outreach")
    if key not in PACKAGES:
        raise HTTPException(400, "Invalid package selected.")
    return key


def stripe_price_for_package(package_key: str) -> str | None:
    return os.getenv(PACKAGES[package_key]["stripe_env"]) or os.getenv("STRIPE_PRICE_ID")


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"alter table {table} add column {column} {definition}")
