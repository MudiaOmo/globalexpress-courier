import re
import unittest

from courier_service_backend import create_app
from courier_service_backend.extensions import db


class CustomerPortalTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def csrf_token(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def register_customer(self):
        token = self.csrf_token("/register")
        return self.client.post("/register", data={
            "csrf_token": token,
            "full_name": "Taylor Customer",
            "email": "taylor@example.com",
            "country": "Nigeria",
            "password": "customer-password",
            "confirm_password": "customer-password",
        })

    def test_customer_can_register_book_and_track_shipment(self):
        response = self.register_customer()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/account")

        booking_token = self.csrf_token("/shipments/new")
        response = self.client.post("/shipments/new", data={
            "csrf_token": booking_token,
            "sender_name": "Taylor Customer",
            "sender_country": "Nigeria",
            "receiver_name": "Jordan Receiver",
            "receiver_country": "Ghana",
            "delivery_address": "12 Market Road, Accra",
            "parcel_description": "Documents",
            "weight": "1.5",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/account")

        account = self.client.get("/account")
        self.assertEqual(account.status_code, 200)
        match = re.search(rb"GEX[A-F0-9]{10}", account.data)
        self.assertIsNotNone(match)
        tracking_number = match.group().decode()

        tracking = self.client.get(f"/track?tracking_number={tracking_number}")
        self.assertEqual(tracking.status_code, 200)
        self.assertIn(b"Tracking history", tracking.data)
        self.assertIn(b"Booking successfully received.", tracking.data)
        self.assertIn(b'class="flight-plane"', tracking.data)
        self.assertIn(b"https://www.google.com/maps/search/?api=1", tracking.data)
        self.assertIn(b"not live GPS tracking", tracking.data)

    def test_customer_pages_require_customer_login_and_keep_admin_separate(self):
        response = self.client.get("/account")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

        self.register_customer()
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/shipments").status_code, 403)

    def test_customer_registration_requires_csrf_token(self):
        response = self.client.post("/register", data={
            "full_name": "Taylor Customer",
            "email": "taylor@example.com",
            "password": "customer-password",
            "confirm_password": "customer-password",
        })
        self.assertEqual(response.status_code, 400)

    def test_customer_api_register_book_track_and_logout(self):
        response = self.client.post("/api/register", json={
            "full_name": "API Customer",
            "email": "api-customer@example.com",
            "password": "customer-password",
            "country": "Nigeria",
        })
        self.assertEqual(response.status_code, 201)

        response = self.client.post("/api/shipments", json={
            "sender_name": "API Customer",
            "sender_country": "Nigeria",
            "receiver_name": "Receiver",
            "receiver_country": "Ghana",
            "delivery_address": "12 Market Road",
            "parcel_description": "Documents",
            "weight": 2.25,
        })
        self.assertEqual(response.status_code, 201)
        tracking_number = response.get_json()["tracking_number"]

        response = self.client.get(f"/api/track/{tracking_number.lower()}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tracking_number"], tracking_number)
        self.assertEqual(len(response.get_json()["history"]), 1)

        response = self.client.get("/api/my-shipments")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["tracking_number"], tracking_number)

        response = self.client.post("/api/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/my-shipments").status_code, 401)

    def test_customer_api_rejects_fields_that_exceed_database_limits(self):
        response = self.client.post("/api/register", json={
            "full_name": "N" * 121,
            "email": "too-long-name@example.com",
            "password": "customer-password",
        })
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/register", json={
            "full_name": "API Customer",
            "email": "api-customer@example.com",
            "password": "customer-password",
            "country": "C" * 101,
        })
        self.assertEqual(response.status_code, 400)

    def test_customer_and_admin_portals_have_separate_navigation(self):
        customer_login = self.client.get("/login")
        self.assertEqual(customer_login.status_code, 200)
        self.assertIn(b'class="customer-auth-page customer-login-page"', customer_login.data)
        self.assertIn(b'class="login-flight-plane"', customer_login.data)
        self.assertIn(b'class="customer-login-background"', customer_login.data)
        self.assertIn(b'images/shipping/container-yard.png', customer_login.data)
        self.assertIn(b'images/shipping/airport-delivery.png', customer_login.data)
        self.assertNotIn(b'href="/admin"', customer_login.data)

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b'id="shipping-gallery-title"', home.data)
        self.assertEqual(home.data.count(b'class="shipping-gallery-card'), 7)
        for image in (
            "container-yard.png",
            "air-cargo-loading.png",
            "aircraft-above-containers.png",
            "ocean-shipping.png",
            "cargo-aircraft.png",
            "air-freight.png",
            "airport-delivery.png",
        ):
            image_response = self.client.get(f"/static/images/shipping/{image}")
            self.assertEqual(image_response.status_code, 200, image)
            image_response.close()

        admin_login = self.client.get("/admin")
        self.assertEqual(admin_login.status_code, 200)
        self.assertIn(b'class="admin-portal"', admin_login.data)
        self.assertIn(b"Customer website", admin_login.data)
        self.assertNotIn(b"Create account", admin_login.data)


if __name__ == "__main__":
    unittest.main()
