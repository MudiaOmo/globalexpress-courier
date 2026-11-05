import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote_plus

from flask import current_app


def send_shipment_status_email(shipment, event):
    settings = current_app.config
    username = settings["SMTP_USERNAME"]
    password = settings["SMTP_PASSWORD"]
    from_address = settings["SMTP_FROM_EMAIL"] or username
    if not username or not password or not from_address:
        return {
            "status": "not_configured",
            "message": "SMTP email is not configured; the status was saved but no email was sent.",
        }

    customer = shipment.customer
    if customer is None or not customer.email:
        return {
            "status": "failed",
            "message": "The shipment customer has no email address; the status was saved but no email was sent.",
        }

    message = EmailMessage()
    message["Subject"] = f"Shipment update: {shipment.tracking_number}"
    message["From"] = from_address
    message["To"] = customer.email
    details = [
        f"Hello {customer.full_name},",
        "",
        f"There is an update for shipment {shipment.tracking_number}.",
        f"Status: {event.status}",
    ]
    if event.location:
        details.append(f"Latest location: {event.location}")
    if event.description:
        details.append(f"Update note: {event.description}")
    details.extend([
        "",
        "View tracking history:",
        (
            f"{settings['PUBLIC_BASE_URL']}/track?tracking_number="
            f"{quote_plus(shipment.tracking_number)}"
        ),
    ])
    message.set_content("\n".join(details))

    try:
        with smtplib.SMTP(
            settings["SMTP_HOST"],
            settings["SMTP_PORT"],
            timeout=15,
        ) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception(
            "Shipment status email failed for %s", shipment.tracking_number
        )
        return {
            "status": "failed",
            "message": "The status was saved, but the notification email could not be sent. Check the SMTP settings and server logs.",
        }

    return {
        "status": "sent",
        "message": f"Status update email sent to {customer.email}.",
    }
