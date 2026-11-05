from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from courier_service_backend.extensions import db


class Customer(UserMixin, db.Model):
    __tablename__ = "customer"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(100))
    language = db.Column(db.String(10), default="en")

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f"<Customer {self.email}>"


class Admin(UserMixin, db.Model):
    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def get_id(self):
        return f"admin:{self.id}"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Shipment(db.Model):
    __tablename__ = "shipment"

    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    customer = db.relationship("Customer", backref=db.backref("shipments", lazy=True))
    sender_name = db.Column(db.String(120), nullable=False)
    sender_country = db.Column(db.String(100), nullable=False)
    receiver_name = db.Column(db.String(120), nullable=False)
    receiver_country = db.Column(db.String(100), nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False)
    parcel_description = db.Column(db.String(255), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Shipment booked", nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tracking_events = db.relationship(
        "TrackingEvent",
        backref="shipment",
        lazy=True,
        order_by="TrackingEvent.created_at",
    )


class TrackingEvent(db.Model):
    __tablename__ = "tracking_event"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipment.id"), nullable=False)
    status = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150))
    description = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
