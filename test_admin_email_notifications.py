import unittest
from unittest.mock import patch

from courier_service_backend import create_app
from courier_service_backend.extensions import db
from courier_service_backend.models import Admin, Customer, Shipment


class AdminEmailNotificationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": 587,
            "SMTP_USERNAME": "courier@example.com",
            "SMTP_PASSWORD": "gmail-app-password",
            "SMTP_FROM_EMAIL": "courier@example.com",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            admin = Admin(email="admin@example.com")
            admin.set_password("a-long-admin-password")
            customer = Customer(
                full_name="Shipment Customer",
                email="customer@example.com",
            )
            customer.set_password("customer-password")
            db.session.add_all([admin, customer])
            db.session.flush()
            self.shipment = Shipment(
                tracking_number="GEX1234567890",
                customer_id=customer.id,
                sender_name="Sender",
                sender_country="Nigeria",
                receiver_name="Receiver",
                receiver_country="Ghana",
                delivery_address="1 Main Road",
                parcel_description="Parcel",
                weight=1.5,
            )
            db.session.add(self.shipment)
            db.session.commit()
        response = self.client.post("/api/admin/login", json={
            "email": "admin@example.com",
            "password": "a-long-admin-password",
        })
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_status_update_sends_email_to_shipment_customer(self):
        with patch("courier_service_backend.email_notifications.smtplib.SMTP") as smtp:
            response = self.client.patch(
                "/api/admin/shipments/GEX1234567890/status",
                json={
                    "status": "In transit",
                    "location": "Accra",
                    "description": "Arrived at sorting facility.",
                },
            )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["email_notification"]["status"], "sent")
        smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        sent_email = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(sent_email["To"], "customer@example.com")
        self.assertIn("In transit", sent_email.get_content())
        self.assertIn("Accra", sent_email.get_content())
        self.assertIn(
            "http://127.0.0.1:5000/track?tracking_number=GEX1234567890",
            sent_email.get_content(),
        )

    def test_status_update_reports_when_email_is_not_configured(self):
        self.app.config.update(
            SMTP_USERNAME="",
            SMTP_PASSWORD="",
            SMTP_FROM_EMAIL="",
        )
        response = self.client.patch(
            "/api/admin/shipments/GEX1234567890/status",
            json={"status": "In transit"},
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["email_notification"]["status"], "not_configured")
        self.assertIn("no email was sent", result["email_notification"]["message"])

    def test_dashboard_exposes_admin_controls_and_shipment_details(self):
        dashboard = self.client.get("/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        for control in (
            b'id="shipment-search"',
            b'id="shipment-status-filter"',
            b'id="export-shipments"',
            b'id="active-count"',
            b'id="delivered-count"',
        ):
            self.assertIn(control, dashboard.data)
        self.assertRegex(
            dashboard.data,
            rb'/static/js/admin-dashboard\.js\?v=\d+',
        )
        self.assertRegex(
            dashboard.data,
            rb'/static/css/site\.css\?v=\d+',
        )

        response = self.client.get("/api/admin/shipments")
        self.assertEqual(response.status_code, 200)
        shipment = response.get_json()[0]
        self.assertEqual(shipment["customer_email"], "customer@example.com")
        self.assertEqual(shipment["delivery_address"], "1 Main Road")
        self.assertEqual(shipment["history"], [])


if __name__ == "__main__":
    unittest.main()
