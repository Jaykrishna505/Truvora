# Truvora Python Realtime Review Platform

This is a Python/FastAPI version of the local business review request platform.

## What It Does

- Business owner signup and login
- Inline login/registration errors without leaving the page
- Forgot-password flow with secure 30-minute, one-time reset links
- Business-type-aware terminology for hotels, restaurants, salons/spas, auto service, healthcare, home services, and other local businesses
- Business dashboard
- Business settings for Google review link, SMS template, email template, and business type
- Review request creation
- Unique public feedback links
- Rating and comments
- Single-use feedback links after a response is recorded
- Private feedback submission for lower ratings
- Google review redirect for higher ratings
- Local Google review button click tracking
- Rating/comment capture before sending a guest to Google
- Realtime dashboard updates with Server-Sent Events
- Delivery log for SMS/email
- Public About Us, Terms and Conditions, and Privacy Policy pages
- Brevo SMTP email support
- Twilio SMS support
- Stripe Checkout-ready payment flow
- Local simulated payment fallback
- 7-day trial
- Paid package gating after trial
- SQLite local database

## Tech Stack

- Python 3.13
- FastAPI
- Uvicorn
- Jinja2 templates
- SQLite
- Vanilla JavaScript
- CSS
- Brevo SMTP for email
- Twilio REST API for SMS
- Stripe Checkout/webhooks for payments

## Folder Structure

```text
python-realtime-review-platform/
  app/
    main.py
    templates/
      index.html
      app.html
      guest.html
      billing.html
      about.html
      terms.html
      privacy.html
    static/
      styles.css
      dashboard.js
      guest.js
      billing.js
  data/
    app.db
  .env.example
  requirements.txt
  README.md
```

## Run In Visual Studio Code

Open this folder in VS Code:

```text
C:\Users\barla\Documents\Codex\2026-06-01\i-need-to-build-a-platform\outputs\python-realtime-review-platform
```

Open a terminal in VS Code and run:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create your `.env` file:

```powershell
Copy-Item .env.example .env
```

Run the app:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000
```

## Brevo Email Setup

If Brevo credentials are blank, email deliveries are recorded locally.

To send real email, fill in `.env`:

```text
BREVO_SMTP_HOST=smtp-relay.brevo.com
BREVO_SMTP_PORT=587
BREVO_SMTP_USER=your_brevo_smtp_login
BREVO_SMTP_PASS=your_brevo_smtp_key
BREVO_FROM_EMAIL=your_verified_sender_email
BREVO_FROM_NAME=Truvora
```

Then restart the app.

Check the dashboard `Deliveries` tab:

```text
provider: brevo
status: sent
```

means email was sent.

Brevo is also used to send password-reset emails. When Brevo is not configured during local development, the forgot-password form displays the local reset link directly on the login page.

## Twilio SMS Setup

If Twilio credentials are blank, SMS deliveries are recorded locally.

To send real SMS, fill in `.env`:

```text
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_PHONE=+15551234567
```

Then restart the app.

Check the dashboard `Deliveries` tab:

```text
provider: twilio
status: sent
```

means SMS was sent.

## Stripe Setup

If Stripe credentials are blank, the app uses local simulated checkout.

The platform has three monthly packages:

| Package | Price | Includes |
|---|---:|---|
| Customer Outreach | $149/month | SMS and email review requests to customers, guests, clients, or patients |
| Reputation Management | $249/month | SMS/email plus replying to online reviews |
| Social Management | $349/month | SMS/email, review replies, and Facebook/social post management |

Every business account gets a 7-day trial. After the trial ends, core platform features are blocked until the business activates one of these packages.

Package cancellation requires 60 days notice. When a business owner requests cancellation, the package remains active until the cancellation effective date. After that date, core platform features are blocked unless the business chooses a package again.

Package changes for active accounts are scheduled for the next renewal date. The current package remains active until that renewal date, then the pending package becomes the active package. Trial or inactive accounts activate the selected package immediately after checkout.

If an account is already cancellation-pending, changing packages asks whether the owner wants to keep the cancellation expiry date or keep the subscription active. Keeping it active clears the pending cancellation and still schedules the package change for the next renewal date.

To use real Stripe Checkout, create three recurring Stripe prices and fill in `.env`:

```text
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PRICE_ID_OUTREACH=price_for_149_package
STRIPE_PRICE_ID_REPUTATION=price_for_249_package
STRIPE_PRICE_ID_SOCIAL=price_for_349_package
STRIPE_WEBHOOK_SECRET=your_webhook_secret
```

Stripe webhook route:

```text
POST /api/payments/webhook
```

## Local Database

The SQLite database is created at:

```text
data\app.db
```

This version uses a clean generic schema:

```text
businesses
review_requests
feedback
deliveries
payments
users
password_resets
```

Key generic columns include:

```text
business_id
business_type
person_name
service_date
review_request_id
```

Because the platform is not live yet, this version intentionally does not include compatibility migrations for older local test databases. If you have an older local `data\app.db`, delete it before running the app so SQLite recreates the clean schema.

For production, migrate to PostgreSQL.

## Business-Type Terminology

Accounts store a `business_type`, and the UI changes terminology based on that type.

| Business type | Person label | Date label |
|---|---|---|
| Hotel | Guest | Stay date |
| Restaurant | Customer | Visit date |
| Salon / Spa | Client | Appointment date |
| Auto Service | Customer | Service date |
| Dental / Medical | Patient | Visit date |
| Home Services | Customer | Service date |
| Other Local Business | Customer | Visit date |

Template variables use only the clean generic placeholders:

```text
{person}
{business}
{link}
```

## Feedback Flow

Each review request creates a unique feedback link. The person selects a star rating and can add comments.

- Ratings below 3 submit private feedback to the business.
- Ratings of 3 or higher record the entered rating/comments locally, track the Google review button click, and then redirect to the business's Google review link.
- After either path is completed, opening the same feedback link again shows that the review was already recorded.

The platform can record what the person entered before leaving for Google, but it cannot confirm whether they actually submitted a Google review on Google's website.

## Stop The App

In the terminal where Uvicorn is running, press:

```text
Ctrl + C
```

## Notes For Live Launch

Before going live:

- Use PostgreSQL instead of SQLite
- Enable HTTPS
- Use a deployed domain in `APP_URL`
- Add secure production session handling
- Add rate limiting
- Add CSRF protection
- Add email verification
- Complete Twilio A2P 10DLC registration for US SMS
- Verify Brevo sender/domain
- Configure Stripe webhooks
