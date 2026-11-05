from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_user, logout_user

from courier_service_backend.extensions import db, socketio
from courier_service_backend.email_notifications import send_shipment_status_email
from courier_service_backend.models import Admin, Shipment, TrackingEvent

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Admin authentication required."}), 401
        if not isinstance(current_user._get_current_object(), Admin):
            return jsonify({"error": "Admin access required."}), 403
        return view(*args, **kwargs)

    return wrapped


def _shipment_json(shipment):
    return {
        "tracking_number": shipment.tracking_number,
        "customer_id": shipment.customer_id,
        "customer_email": shipment.customer.email if shipment.customer else None,
        "sender_name": shipment.sender_name,
        "sender_country": shipment.sender_country,
        "receiver_name": shipment.receiver_name,
        "receiver_country": shipment.receiver_country,
        "delivery_address": shipment.delivery_address,
        "parcel_description": shipment.parcel_description,
        "weight": shipment.weight,
        "status": shipment.status,
        "created_at": shipment.created_at.isoformat(),
        "history": [
            {
                "status": event.status,
                "location": event.location,
                "description": event.description,
                "date": event.created_at.isoformat(),
            }
            for event in shipment.tracking_events
        ],
    }


@admin_bp.post("/login")
def admin_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Invalid email or password."}), 401

    admin = Admin.query.filter_by(email=email.strip().lower()).first()
    if not admin or not admin.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    login_user(admin)
    return jsonify({"message": "Admin login successful."})


@admin_bp.post("/logout")
@admin_required
def admin_logout():
    logout_user()
    return jsonify({"message": "Admin logged out successfully."})


@admin_bp.get("/shipments")
@admin_required
def list_shipments():
    shipments = Shipment.query.order_by(Shipment.created_at.desc()).all()
    return jsonify([_shipment_json(shipment) for shipment in shipments])


@admin_bp.patch("/shipments/<tracking_number>/status")
@admin_required
def update_shipment_status(tracking_number):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    status = data.get("status")
    location = data.get("location", "")
    description = data.get("description", "")
    if not isinstance(status, str) or not status.strip() or len(status.strip()) > 50:
        return jsonify({"error": "Status must be between 1 and 50 characters."}), 400
    if (
        not isinstance(location, str)
        or len(location.strip()) > 150
        or not isinstance(description, str)
        or len(description.strip()) > 255
    ):
        return jsonify({"error": "Invalid location or description."}), 400

    shipment = Shipment.query.filter_by(
        tracking_number=tracking_number.upper()
    ).first()
    if shipment is None:
        return jsonify({"error": "Tracking number not found."}), 404

    shipment.status = status.strip()
    event = TrackingEvent(
        shipment=shipment,
        status=shipment.status,
        location=location.strip() or None,
        description=description.strip() or None,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    db.session.commit()
    email_notification = send_shipment_status_email(shipment, event)

    update = {
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "location": event.location,
        "description": event.description,
        "date": event.created_at.isoformat(),
    }
    socketio.emit(
        "tracking_update",
        update,
        to=shipment.tracking_number,
        namespace="/",
    )
    current_app.logger.info(
        "Admin updated shipment status for %s", shipment.tracking_number
    )
    return jsonify({
        "message": "Shipment status updated.",
        "shipment": update,
        "email_notification": email_notification,
    })
