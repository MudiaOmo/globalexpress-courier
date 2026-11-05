import secrets
from functools import wraps
from math import isfinite

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, logout_user

from courier_service_backend.extensions import db
from courier_service_backend.models import Admin, Customer, Shipment, TrackingEvent

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Customer authentication required."}), 401
        if isinstance(current_user._get_current_object(), Admin):
            return jsonify({"error": "Customer access required."}), 403
        return view(*args, **kwargs)

    return wrapped


@api_bp.post("/register")
def register():
    data = _json_object()
    if data is None:
        return jsonify({"error": "Request body must be a JSON object."}), 400

    name = data.get("full_name")
    email = data.get("email")
    password = data.get("password")
    if (
        not isinstance(name, str)
        or not isinstance(email, str)
        or not isinstance(password, str)
        or not name.strip()
        or len(name.strip()) > 120
        or not email.strip()
        or len(email.strip()) > 150
        or "@" not in email
        or len(password) < 8
    ):
        return jsonify({
            "error": "Enter your name, email and password of at least 8 characters."
        }), 400

    email = email.strip().lower()
    if Customer.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    country = data.get("country", "")
    language = data.get("language", "en")
    if (
        not isinstance(country, str)
        or len(country.strip()) > 100
        or not isinstance(language, str)
        or len(language.strip()) > 10
    ):
        return jsonify({"error": "Country and language must be valid text values."}), 400

    customer = Customer(
        full_name=name.strip(),
        email=email,
        country=country.strip(),
        language=language.strip() or "en",
    )
    customer.set_password(password)
    db.session.add(customer)
    db.session.commit()
    login_user(customer)
    return jsonify({"message": "Account successfully created."}), 201


@api_bp.post("/login")
def login():
    data = _json_object()
    if data is None:
        return jsonify({"error": "Request body must be a JSON object."}), 400

    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid email or password."}), 401

    customer = Customer.query.filter_by(email=email.strip().lower()).first()
    if not customer or not customer.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    login_user(customer)
    return jsonify({"message": "Login successful.", "customer": customer.full_name})


@api_bp.post("/logout")
@customer_required
def logout():
    logout_user()
    return jsonify({"message": "Successfully logged out."})


@api_bp.post("/shipments")
@customer_required
def book_shipment():
    data = _json_object()
    if data is None:
        return jsonify({"error": "Request body must be a JSON object."}), 400

    required_fields = (
        "sender_name",
        "sender_country",
        "receiver_name",
        "receiver_country",
        "delivery_address",
        "parcel_description",
    )
    max_lengths = {
        "sender_name": 120,
        "sender_country": 100,
        "receiver_name": 120,
        "receiver_country": 100,
        "delivery_address": 255,
        "parcel_description": 255,
    }
    if any(
        not isinstance(data.get(field), str)
        or not data[field].strip()
        or len(data[field].strip()) > max_lengths[field]
        for field in required_fields
    ):
        return jsonify({"error": "Please complete all shipment fields."}), 400

    try:
        weight = float(data["weight"])
        if not isfinite(weight) or weight <= 0 or weight > 1000:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid parcel weight."}), 400

    tracking_number = f"GEX{secrets.token_hex(5).upper()}"
    while Shipment.query.filter_by(tracking_number=tracking_number).first():
        tracking_number = f"GEX{secrets.token_hex(5).upper()}"
    shipment = Shipment(
        tracking_number=tracking_number,
        customer_id=current_user.id,
        sender_name=data["sender_name"].strip(),
        sender_country=data["sender_country"].strip(),
        receiver_name=data["receiver_name"].strip(),
        receiver_country=data["receiver_country"].strip(),
        delivery_address=data["delivery_address"].strip(),
        parcel_description=data["parcel_description"].strip(),
        weight=weight,
    )
    db.session.add(shipment)
    db.session.flush()
    db.session.add(TrackingEvent(
        shipment_id=shipment.id,
        status=shipment.status,
        location=shipment.sender_country,
        description="Booking successfully received.",
    ))
    db.session.commit()

    return jsonify({
        "message": "Shipment booked successfully.",
        "tracking_number": tracking_number,
    }), 201


@api_bp.get("/track/<tracking_number>")
def track_shipment(tracking_number):
    shipment = Shipment.query.filter_by(
        tracking_number=tracking_number.upper()
    ).first()
    if shipment is None:
        return jsonify({"error": "Tracking number not found."}), 404

    history = [
        {
            "status": event.status,
            "location": event.location,
            "description": event.description,
            "date": event.created_at.isoformat(),
        }
        for event in shipment.tracking_events
    ]
    return jsonify({
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "destination": shipment.receiver_country,
        "history": history,
    })


@api_bp.get("/my-shipments")
@customer_required
def my_shipments():
    shipments = Shipment.query.filter_by(customer_id=current_user.id).all()
    return jsonify([
        {
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "destination": shipment.receiver_country,
            "weight": shipment.weight,
        }
        for shipment in shipments
    ])
