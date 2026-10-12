from flask import Blueprint, request, jsonify, current_app
import os
import re
from datetime import datetime

from flask import Blueprint, request, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.errors import DuplicateKeyError

from mongodb import users_collection


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

TOKEN_MAX_AGE_SECONDS = 12 * 60 * 60

# Configure SMARTEMS_SECRET_KEY as an environment variable for deployment.
# The fallback is only for local development.
SECRET_KEY = os.environ.get(
    "SMARTEMS_SECRET_KEY",
    "smartems-local-development-key-change-before-deployment",
)

serializer = URLSafeTimedSerializer(
    SECRET_KEY,
    salt="smartems-auth-v1",
)


def utc_now():
    return datetime.utcnow()


def normalize_email(email):
    if not isinstance(email, str):
        return ""

    return email.strip().lower()


def is_admin_user(user):
    """Recognize supported administrator role fields."""
    return (
        str(user.get("role", "")).strip().lower() == "admin"
        or str(user.get("user_type", "")).strip().lower() == "admin"
        or str(user.get("account_type", "")).strip().lower() == "admin"
        or user.get("is_admin") is True
        or user.get("isAdmin") is True
    )


def issue_token(user):
    return serializer.dumps({
        "user_id": str(user["_id"]),
        "email": normalize_email(user.get("email", "")),
        "role": "admin" if is_admin_user(user) else "user",
    })


def verify_and_migrate_password(user, submitted_password):
    """
    Verify modern password hashes and support older accounts that
    may have stored a password in either 'password_hash' or 'password'.

    A legacy plaintext password is converted to a hash after a
    successful login. New accounts always use password_hash.
    """
    stored_hash = user.get("password_hash")

    if isinstance(stored_hash, str) and stored_hash:
        try:
            if check_password_hash(stored_hash, submitted_password):
                return True
        except (ValueError, TypeError):
            pass

    legacy_value = user.get("password")

    if not isinstance(legacy_value, str) or not legacy_value:
        return False

    # Check whether the legacy field contains a Werkzeug hash.
    if legacy_value.startswith((
        "pbkdf2:",
        "scrypt:",
    )):
        try:
            valid = check_password_hash(
                legacy_value,
                submitted_password,
            )
        except (ValueError, TypeError):
            valid = False
    else:
        # Compatibility for existing plaintext-password records.
        valid = legacy_value == submitted_password

    if not valid:
        return False

    # Migrate a successfully verified legacy credential.
    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": generate_password_hash(
                    submitted_password
                ),
                "updated_at": utc_now(),
            },
            "$unset": {
                "password": "",
            },
        },
    )

    return True


def find_user_by_email(email):
    return users_collection.find_one({
        "email": normalize_email(email)
    })


def authenticate(email, password, admin_only=False):
    normalized_email = normalize_email(email)

    if not normalized_email or not isinstance(password, str) or not password:
        return None, "Email and password are required."

    user = find_user_by_email(normalized_email)

    if not user or not verify_and_migrate_password(user, password):
        return None, "Invalid email or password."

    admin = is_admin_user(user)

    if admin_only and not admin:
        return None, "This account does not have administrator access."

    if not admin_only and admin:
        return None, "Please use the Admin Login page."

    return user, None


def get_current_user():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None, "Authentication token is required."

    try:
        payload = serializer.loads(
            token.strip(),
            max_age=TOKEN_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        return None, "Your session has expired. Please sign in again."
    except BadSignature:
        return None, "Invalid authentication token."

    user_id = payload.get("user_id")

    if not user_id:
        return None, "Invalid authentication token."

    from bson import ObjectId

    if not ObjectId.is_valid(user_id):
        return None, "Invalid authentication token."

    user = users_collection.find_one({
        "_id": ObjectId(user_id)
    })

    if not user:
        return None, "Account not found."

    return user, None


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    name = data.get("name", "")
    email = normalize_email(data.get("email"))
    phone = data.get("phone", "")
    password = data.get("password", "")

    if not isinstance(name, str) or not name.strip():
        return jsonify({
            "success": False,
            "message": "Full name is required.",
        }), 400

    if len(name.strip()) > 120:
        return jsonify({
            "success": False,
            "message": "Full name is too long.",
        }), 400

    if not email or len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email,
    ):
        return jsonify({
            "success": False,
            "message": "Enter a valid email address.",
        }), 400

    if not isinstance(phone, str) or not phone.strip():
        return jsonify({
            "success": False,
            "message": "Phone number is required.",
        }), 400

    if len(phone.strip()) > 30:
        return jsonify({
            "success": False,
            "message": "Phone number is too long.",
        }), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 8 characters.",
        }), 400

    try:
        if find_user_by_email(email):
            return jsonify({
                "success": False,
                "message": "An account with this email already exists.",
            }), 409

        user_record = {
            "name": name.strip(),
            "email": email,
            "phone": phone.strip(),
            "password_hash": generate_password_hash(password),
            "role": "user",
            "created_at": utc_now(),
        }

        result = users_collection.insert_one(user_record)

        return jsonify({
            "success": True,
            "message": "Account created successfully. Please sign in.",
            "user_id": str(result.inserted_id),
        }), 201

    except DuplicateKeyError:
        return jsonify({
            "success": False,
            "message": "An account with this email already exists.",
        }), 409

    except Exception:
        auth_bp.logger.exception("Signup failed")

        return jsonify({
            "success": False,
            "message": "Unable to create the account right now.",
        }), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    user, error = authenticate(
        data.get("email"),
        data.get("password"),
        admin_only=False,
    )

    if error:
        return jsonify({
            "success": False,
            "message": error,
        }), 401

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "token": issue_token(user),
        "role": "user",
        "user": {
            "name": user.get("name", ""),
            "email": normalize_email(user.get("email", "")),
            "phone": user.get("phone", ""),
        },
    }), 200


@auth_bp.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    user, error = authenticate(
        data.get("email"),
        data.get("password"),
        admin_only=True,
    )

    if error:
        return jsonify({
            "success": False,
            "message": error,
        }), 401

    return jsonify({
        "success": True,
        "message": "Administrator login successful.",
        "token": issue_token(user),
        "role": "admin",
        "user": {
            "name": user.get("name", ""),
            "email": normalize_email(user.get("email", "")),
        },
    }), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    user, error = get_current_user()

    if error:
        return jsonify({
            "success": False,
            "message": error,
        }), 401

    return jsonify({
        "success": True,
        "user": {
            "name": user.get("name", ""),
            "email": normalize_email(user.get("email", "")),
            "role": "admin" if is_admin_user(user) else "user",
        },
    }), 200
