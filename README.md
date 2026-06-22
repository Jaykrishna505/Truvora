# Truvora Python Realtime Review Platform

This is a Python/FastAPI version of the hotel review request platform.

## What It Does

- Hotel owner signup and login
- Inline login/registration errors without leaving the page
- Forgot-password flow with secure 30-minute, one-time reset links
- Hotel dashboard
- Hotel settings for Google review link, SMS template, and email template
- Guest request creation
- Unique public guest feedback links
- Guest rating and comments
- Review flow:
  - Submit feedback privately
  - Leave a Google review
- Realtime dashboard updates with Server-Sent Events
- Delivery log for SMS/email
- Brevo SMTP email support
- Twilio SMS support
- Stripe Checkout-ready payment flow
- Local simulated payment fallback
- 7-day hotel trial
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
| Guest Outreach | $149/month | SMS and email review requests to guests |
| Reputation Management | $249/month | SMS/email plus replying to online reviews |
| Social Management | $349/month | SMS/email, review replies, and Facebook/social post management |

Every hotel account gets a 7-day trial. After the trial ends, core platform features are blocked until the hotel activates one of these packages.

Package cancellation requires 60 days notice. When a hotel owner requests cancellation, the package remains active until the cancellation effective date. After that date, core platform features are blocked unless the hotel chooses a package again.

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

For production, migrate to PostgreSQL.

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
- Add password reset
- Add email verification
- Complete Twilio A2P 10DLC registration for US SMS
- Verify Brevo sender/domain
- Configure Stripe webhooks
