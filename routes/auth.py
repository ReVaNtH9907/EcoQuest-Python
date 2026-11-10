"""
EcoQuest — Authentication Routes.

Implements registration with image validation, email OTP verification,
credential validation, session management, and logout.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    g,
    jsonify,
)
from models import db, User
from services import (
    register_user,
    authenticate_user,
    create_email_otp,
    verify_email_otp,
    can_resend_otp,
    send_otp_email,
    csrf_protect,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@csrf_protect
def register():
    """Member registration endpoint with avatar upload and validation."""
    # API / JSON support
    if request.headers.get("Accept") == "application/json" and request.method == "GET":
        return jsonify(message="Auth · register endpoint ready"), 200

    # If already logged in, redirect to profile
    if getattr(g, "current_user", None):
        return redirect(url_for("profile.view_profile"))

    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        city = request.form.get("city")
        college = request.form.get("college")
        profile_picture = request.files.get("profile_picture")

        user, message = register_user(
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            confirm_password=confirm_password,
            city=city,
            college=college,
            profile_picture_file=profile_picture,
        )

        if not user:
            flash(message, "error")
            return render_template(
                "auth/register.html",
                form_data={
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "city": city,
                    "college": college,
                },
            ), 400

        # Registration succeeded: Create and dispatch OTP
        _, otp_code = create_email_otp(user.id, purpose="email_verification")
        email_result = send_otp_email(user.email, otp_code, user.full_name)

        # Store pending verification ID in session
        session["pending_verification_user_id"] = user.id

        if email_result["mode"] == "development":
            flash(
                f"[DEVELOPMENT MODE] Real email delivery skipped: SMTP not configured. "
                f"Your 6-digit verification code is: {otp_code} (Valid for 5 minutes).",
                "info",
            )
        else:
            flash("Account created! Please check your email for the 6-digit verification code.", "success")

        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/register.html", form_data={})


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
@csrf_protect
def verify_otp():
    """Verify 6-digit email OTP to activate member account."""
    user_id = session.get("pending_verification_user_id")

    # If user is already authenticated, check if they need verification
    if not user_id and getattr(g, "current_user", None):
        user_id = g.current_user.id

    if not user_id:
        flash("No pending verification found. Please log in or register.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        session.pop("pending_verification_user_id", None)
        flash("User record not found. Please register again.", "error")
        return redirect(url_for("auth.register"))

    if user.email_verified and not getattr(g, "current_user", None):
        session.pop("pending_verification_user_id", None)
        session["user_id"] = user.id
        return redirect(url_for("profile.view_profile"))

    if request.method == "POST":
        code = request.form.get("otp_code")
        success, message = verify_email_otp(user_id, code, purpose="email_verification")

        if success:
            session.pop("pending_verification_user_id", None)
            session["user_id"] = user.id
            session.permanent = True
            flash("Email verified successfully! Welcome to EcoQuest.", "success")
            return redirect(url_for("profile.view_profile"))

        flash(message, "error")
        return render_template("auth/verify_otp.html", user=user), 400

    return render_template("auth/verify_otp.html", user=user)


@auth_bp.route("/resend-otp", methods=["POST"])
@csrf_protect
def resend_otp():
    """Resend email verification code with rate-limit protection."""
    user_id = session.get("pending_verification_user_id")
    if not user_id and getattr(g, "current_user", None):
        user_id = g.current_user.id

    if not user_id:
        flash("Session expired. Please log in.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("auth.register"))

    can_resend, remaining = can_resend_otp(user_id, purpose="email_verification", cooldown_seconds=60)
    if not can_resend:
        flash(f"Please wait {remaining} seconds before requesting a new code.", "warning")
        return redirect(url_for("auth.verify_otp"))

    _, otp_code = create_email_otp(user.id, purpose="email_verification")
    email_result = send_otp_email(user.email, otp_code, user.full_name)

    if email_result["mode"] == "development":
        flash(
            f"[DEVELOPMENT MODE] Real email delivery skipped: SMTP not configured. "
            f"Your new 6-digit verification code is: {otp_code} (Valid for 5 minutes).",
            "info",
        )
    else:
        flash("A fresh verification code has been dispatched to your email address.", "info")

    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/login", methods=["GET", "POST"])
@csrf_protect
def login():
    """Member sign-in endpoint with session initialization."""
    # API / JSON support
    if request.headers.get("Accept") == "application/json" and request.method == "GET":
        return jsonify(message="Auth · login endpoint ready"), 200

    if getattr(g, "current_user", None):
        return redirect(url_for("profile.view_profile"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = bool(request.form.get("remember_me"))

        user, message = authenticate_user(email, password)

        if not user:
            flash(message, "error")
            return render_template("auth/login.html", email=email), 401

        # Establish authenticated session
        session.clear()
        session["user_id"] = user.id
        if remember:
            session.permanent = True

        flash(f"Welcome back, {user.full_name}!", "success")

        # Next redirection
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("profile.view_profile"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Terminate the authenticated session safely."""
    # API / JSON support
    if request.headers.get("Accept") == "application/json":
        session.clear()
        return jsonify(message="Auth · logout endpoint ready"), 200

    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@csrf_protect
def forgot_password():
    """Password reset request endpoint."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            _, otp_code = create_email_otp(user.id, purpose="password_reset")
            res = send_otp_email(user.email, otp_code, user.full_name)
            if res["mode"] == "development":
                flash(
                    f"[DEVELOPMENT MODE] SMTP not configured. Password reset code: {otp_code}",
                    "info",
                )
            else:
                flash("If an account exists with that email, a reset code was sent.", "info")
        else:
            flash("If an account exists with that email, a reset code was sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")
