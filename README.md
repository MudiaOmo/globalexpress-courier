# Courier service backend

This folder contains the Flask backend. Public customer routes and admin routes are
separated into their own modules.

## Setup

From this folder, create and activate a virtual environment, then install
dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a private, persistent `SECRET_KEY` and enter an admin email and password in
`.env` before running the server. An admin account is created on first startup
when both admin settings are configured. The admin password must contain at
least 12 characters. If those settings are blank, no admin account is created.

To allow an additional admin account to be registered from `/admin/register`,
set `ADMIN_REGISTRATION_TOKEN` in `.env` to a long, private value and share it
only with trusted admins. The registration page explains when this setting is
missing. If there are no admin accounts in the database, the first admin may
be created once without an invite token to bootstrap the portal. After that,
additional admin registrations require the configured token. Each admin
password must contain at least 12 characters.

Run the app with:

```powershell
python run.py
```

The website and API listen on `http://127.0.0.1:5000`.

## Website pages

- `/` — courier landing page and shipment lookup form
- `/track` — shipment history page (provide `tracking_number` as a query parameter)
- `/register` — customer account registration
- `/login` — customer sign-in
- `/account` — signed-in customer's shipments
- `/shipments/new` — create a shipment while signed in
- `/admin` — admin sign-in
- `/admin/register` — admin registration (requires `ADMIN_REGISTRATION_TOKEN`)
- `/admin/dashboard` — admin-only shipment dashboard with search, status filters,
  shipment-history details, CSV export, status counts, and update controls

Website templates live in `courier_service_backend/templates/`; CSS and JavaScript
assets live in `courier_service_backend/static/`.

Customers can register on the website, book deliveries, and track each delivery
from their account. The admin portal is separate and remains restricted to
accounts provisioned through `ADMIN_EMAIL` and `ADMIN_PASSWORD`.

### Shipment status email notifications

When an admin posts a shipment status update, the server emails the address on
the customer's account. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, optionally `SMTP_FROM_EMAIL`, and the public `PUBLIC_BASE_URL`
in `.env`. For Gmail, use
`smtp.gmail.com`, port `587`, and a Google App Password (not the normal Google
account password); App Passwords require 2-Step Verification. If SMTP is not
configured or delivery fails, the admin dashboard reports that the status was
saved but the email was not sent, and the server logs the delivery error.

The tracking page includes a Google Maps search link for the latest location
entered by an admin. It uses the reported place name only and is not live GPS
tracking. An animated airplane illustrates shipment progress without claiming
to represent real-time location.

## Admin API

- `POST /api/admin/login` — JSON `{ "email": "...", "password": "..." }`
- `POST /api/admin/logout`
- `GET /api/admin/shipments`
- `PATCH /api/admin/shipments/<tracking_number>/status` — JSON fields:
  `status` (required), `location` and `description` (optional)

Login uses a session cookie. The status endpoint adds a tracking-history event
and emits a Socket.IO `tracking_update` event to clients in that shipment's
tracking room.

## Customer API

Existing routes are retained: `POST /api/register`, `POST /api/login`,
`POST /api/logout`, `POST /api/shipments`, `GET /api/track/<tracking_number>`,
and `GET /api/my-shipments`.
