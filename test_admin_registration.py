import re
import unittest

from courier_service_backend import create_app
from courier_service_backend.extensions import db
from courier_service_backend.models import Admin


class AdminRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "ADMIN_REGISTRATION_TOKEN": "private-registration-token",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def csrf_token(self):
        response = self.client.get("/admin/register")
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def registration_form(self, **overrides):
        data = {
            "csrf_token": self.csrf_token(),
            "email": "operations@example.com",
            "password": "a-very-long-admin-password",
            "confirm_password": "a-very-long-admin-password",
            "registration_token": "private-registration-token",
        }
        data.update(overrides)
        return self.client.post("/admin/register", data=data)

    def test_admin_can_create_account_with_registration_token(self):
        response = self.registration_form()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/dashboard")

        with self.app.app_context():
            admin = Admin.query.filter_by(email="operations@example.com").first()
            self.assertIsNotNone(admin)
            self.assertTrue(admin.check_password("a-very-long-admin-password"))

        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)

    def test_registration_rejects_invalid_token_and_short_password(self):
        response = self.registration_form(registration_token="wrong-token")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"registration token is invalid", response.data)

        response = self.registration_form(
            password="short",
            confirm_password="short",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"at least 12 characters", response.data)

        with self.app.app_context():
            self.assertEqual(Admin.query.count(), 0)

    def test_first_admin_can_register_without_invite_then_registration_closes(self):
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "ADMIN_REGISTRATION_TOKEN": "",
        })
        try:
            client = app.test_client()
            response = client.get("/admin/register")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Create the first admin account", response.data)
            self.assertIn(b'name="email"', response.data)
            self.assertNotIn(b'name="registration_token"', response.data)

            match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
            self.assertIsNotNone(match)
            response = client.post("/admin/register", data={
                "csrf_token": match.group(1).decode(),
                "email": "first-admin@example.com",
                "password": "a-very-long-admin-password",
                "confirm_password": "a-very-long-admin-password",
            })
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/admin/dashboard")

            another_client = app.test_client()
            response = another_client.get("/admin/register")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Admin registration is disabled", response.data)
            self.assertNotIn(b'name="email"', response.data)
        finally:
            with app.app_context():
                db.session.remove()
                db.drop_all()


if __name__ == "__main__":
    unittest.main()
