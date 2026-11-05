import secrets
from math import isfinite
from urllib.parse import quote_plus

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, logout_user

from courier_service_backend.extensions import db
from courier_service_backend.models import Admin, Customer, Shipment, TrackingEvent

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def home():
    return render_template("index.html")


@web_bp.get("/track")
def track():
    tracking_number = request.args.get("tracking_number", "").strip().upper()
    shipment = None
    searched = bool(tracking_number)
    if tracking_number:
        shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
    latest_location = None
    maps_url = None
    if shipment:
        latest_event = shipment.tracking_events[-1] if shipment.tracking_events else None
        latest_location = latest_event.location if latest_event else None
        if latest_location:
            maps_url = (
                "https://www.google.com/maps/search/?api=1&query="
                f"{quote_plus(latest_location)}"
            )
    return render_template(
        "tracking.html",
        tracking_number=tracking_number,
        shipment=shipment,
        searched=searched,
        latest_location=latest_location,
        maps_url=maps_url,
    ), 200 if shipment or not searched else 404


@web_bp.route("/register", methods=["GET", "POST"])
def customer_register():
    if current_user.is_authenticated:
        if isinstance(current_user._get_current_object(), Admin):
            return redirect(url_for("web.admin_dashboard"))
        return redirect(url_for("web.customer_account"))

    if request.method == "POST":
        if not _valid_csrf():
            abort(400, description="Invalid form token. Please reload and try again.")

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        country = request.form.get("country", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if (
            not full_name
            or len(full_name) > 120
            or not email
            or len(email) > 150
            or "@" not in email
            or len(country) > 100
            or len(password) < 8
        ):
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif Customer.query.filter_by(email=email).first():
            flash("That email is already registered. Please sign in instead.", "error")
        else:
            customer = Customer(
                full_name=full_name,
                email=email,
                country=country or None,
            )
            customer.set_password(password)
            db.session.add(customer)
            db.session.commit()
            login_user(customer)
            flash("Your account is ready. You can now book and track shipments.", "success")
            return redirect(url_for("web.customer_account"))

    return render_template("customer_register.html")


@web_bp.route("/login", methods=["GET", "POST"])
def customer_login():
    if current_user.is_authenticated:
        if isinstance(current_user._get_current_object(), Admin):
            return redirect(url_for("web.admin_dashboard"))
        return redirect(url_for("web.customer_account"))

    if request.method == "POST":
        if not _valid_csrf():
            abort(400, description="Invalid form token. Please reload and try again.")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        customer = Customer.query.filter_by(email=email).first()
        if not customer or not customer.check_password(password):
            flash("Email or password is incorrect.", "error")
        else:
            login_user(customer)
            return redirect(url_for("web.customer_account"))

    return render_template("customer_login.html")


@web_bp.post("/logout")
def customer_logout():
    if not _valid_csrf():
        abort(400, description="Invalid form token. Please reload and try again.")
    if current_user.is_authenticated and isinstance(
        current_user._get_current_object(), Admin
    ):
        abort(403)
    logout_user()
    flash("You have signed out.", "success")
    return redirect(url_for("web.home"))


@web_bp.get("/account")
def customer_account():
    customer = _current_customer()
    if customer is None:
        return redirect(url_for("web.customer_login"))
    shipments = Shipment.query.filter_by(customer_id=customer.id).order_by(
        Shipment.created_at.desc()
    ).all()
    return render_template("customer_account.html", customer=customer, shipments=shipments)


@web_bp.route("/shipments/new", methods=["GET", "POST"])
def new_shipment():
    customer = _current_customer()
    if customer is None:
        return redirect(url_for("web.customer_login"))

    if request.method == "POST":
        if not _valid_csrf():
            abort(400, description="Invalid form token. Please reload and try again.")

        field_names = (
            "sender_name",
            "sender_country",
            "receiver_name",
            "receiver_country",
            "delivery_address",
            "parcel_description",
        )
        values = {name: request.form.get(name, "").strip() for name in field_names}
        max_lengths = {
            "sender_name": 120,
            "sender_country": 100,
            "receiver_name": 120,
            "receiver_country": 100,
            "delivery_address": 255,
            "parcel_description": 255,
        }
        try:
            weight = float(request.form.get("weight", ""))
            valid_weight = isfinite(weight) and 0 < weight <= 1000
        except ValueError:
            valid_weight = False
            weight = 0

        if (
            any(not value or len(value) > max_lengths[name] for name, value in values.items())
            or not valid_weight
        ):
            flash("Complete every field and enter a parcel weight from 0 to 1000 kg.", "error")
            return render_template("shipment_booking.html", form_values=request.form)

        tracking_number = f"GEX{secrets.token_hex(5).upper()}"
        while Shipment.query.filter_by(tracking_number=tracking_number).first():
            tracking_number = f"GEX{secrets.token_hex(5).upper()}"

        shipment = Shipment(
            tracking_number=tracking_number,
            customer_id=customer.id,
            sender_name=values["sender_name"],
            sender_country=values["sender_country"],
            receiver_name=values["receiver_name"],
            receiver_country=values["receiver_country"],
            delivery_address=values["delivery_address"],
            parcel_description=values["parcel_description"],
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
        flash(f"Shipment booked. Your tracking number is {tracking_number}.", "success")
        return redirect(url_for("web.customer_account"))

    return render_template("shipment_booking.html", form_values={})


@web_bp.get("/admin")
def admin_login_page():
    if current_user.is_authenticated:
        if isinstance(current_user._get_current_object(), Admin):
            return redirect(url_for("web.admin_dashboard"))
        abort(403)
    return render_template(
        "admin_login.html",
        registration_enabled=bool(current_app.config["ADMIN_REGISTRATION_TOKEN"]),
    )


@web_bp.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    registration_token = current_app.config["ADMIN_REGISTRATION_TOKEN"]
    first_admin_setup = Admin.query.count() == 0

    if current_user.is_authenticated:
        if isinstance(current_user._get_current_object(), Admin):
            return redirect(url_for("web.admin_dashboard"))
        abort(403)

    registration_enabled = bool(registration_token) or first_admin_setup

    if request.method == "POST" and registration_enabled:
        if not _valid_csrf():
            abort(400, description="Invalid form token. Please reload and try again.")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        submitted_token = request.form.get("registration_token", "")

        if registration_token and not secrets.compare_digest(submitted_token, registration_token):
            flash("The admin registration token is invalid.", "error")
        elif not registration_token and Admin.query.count() != 0:
            abort(403)
        elif not email or len(email) > 150 or "@" not in email:
            flash("Enter a valid email address.", "error")
        elif len(password) < 12:
            flash("Admin passwords must contain at least 12 characters.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif Admin.query.filter_by(email=email).first():
            flash("An admin account already uses that email.", "error")
        else:
            admin = Admin(email=email)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            login_user(admin)
            flash("Admin account created. Welcome to the operations portal.", "success")
            return redirect(url_for("web.admin_dashboard"))

    return render_template(
        "admin_register.html",
        registration_enabled=registration_enabled,
        first_admin_setup=first_admin_setup,
        token_required=bool(registration_token),
    )


@web_bp.get("/admin/dashboard")
def admin_dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for("web.admin_login_page"))
    if not isinstance(current_user._get_current_object(), Admin):
        abort(403)
    return render_template("admin_dashboard.html", admin=current_user)


def _current_customer():
    if not current_user.is_authenticated:
        return None
    user = current_user._get_current_object()
    if isinstance(user, Admin):
        abort(403)
    return user


def _valid_csrf():
    from flask import session

    submitted = request.form.get("csrf_token", "")
    expected = session.get("_csrf_token", "")
    return bool(submitted and expected and secrets.compare_digest(submitted, expected))
