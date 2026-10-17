import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import Response

from app import main


class CookieTest(unittest.TestCase):
    def test_public_cookie_requires_https(self):
        with patch.object(main, "PUBLIC_DEPLOYMENT", True):
            response = Response()
            main.set_session(response, 1)
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])

    def test_local_cookie_works_without_https(self):
        with patch.object(main, "PUBLIC_DEPLOYMENT", False):
            response = Response()
            main.set_session(response, 1)
        self.assertNotIn("Secure", response.headers["set-cookie"])


class PublicAccessTest(unittest.IsolatedAsyncioTestCase):
    async def test_public_payment_and_reset_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with (
                patch.object(main, "DATA_DIR", data),
                patch.object(main, "DB_PATH", data / "app.db"),
                patch.object(main, "PUBLIC_DEPLOYMENT", True),
                patch.dict("os.environ", {"STRIPE_SECRET_KEY": "", "STRIPE_WEBHOOK_SECRET": ""}),
                patch.object(main, "send_email", AsyncMock(return_value={"provider": "local"})),
            ):
                main.init_db()
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app), base_url="https://test"
                ) as client:
                    signup = await client.post("/api/auth/register", json={
                        "businessName": "Public Test", "businessType": "restaurant",
                        "email": "public@example.test", "password": "public-test-password",
                    })
                    self.assertEqual(signup.status_code, 200)
                    self.assertEqual((await client.get("/api/me")).status_code, 200)
                    simulated = await client.post("/api/payments/simulate", json={"packageKey": "outreach"})
                    self.assertEqual(simulated.status_code, 403)
                    checkout = await client.post("/api/payments/checkout", json={"packageKey": "outreach"})
                    self.assertEqual(checkout.status_code, 503)
                    webhook = await client.post("/api/payments/webhook", json={"type": "checkout.session.completed"})
                    self.assertEqual(webhook.status_code, 503)
                    reset = await client.post("/api/auth/forgot-password", json={"email": "public@example.test"})
                    self.assertEqual(reset.status_code, 200)
                    self.assertNotIn("resetUrl", reset.json())
                    self.assertNotIn("local reset link", reset.text)
                    me = await client.get("/api/me")
                    self.assertNotEqual(me.json()["business"]["paymentStatus"], "active")
