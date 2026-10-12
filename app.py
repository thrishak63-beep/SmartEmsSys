
from auth_service import auth_bp, get_current_user
from hospital_service import hospital_bp
from pymongo.errors import DuplicateKeyError
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from pymongo import ReturnDocument
from bson import ObjectId
import uuid
import math

from triage_model import predict_triage
from triage_questions import get_questions, get_supported_emergencies
from triage_session import TriageSession
from triage_data import build_patient_data
from adaptive_triage import (
    identify_emergency_type,
    extract_known_answers,
)

from mongodb import (
    users_collection,
    emergencies_collection,
    triage_collection,
    ambulances_collection,
    hospitals_collection,
    dispatch_collection,
)


app = Flask(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(hospital_bp)
CORS(app)

ACTIVE_STATUS = "En Route"
sessions = {}


# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.utcnow()


def get_missing_features(patient_data):
    missing = []

    for feature, value in patient_data.items():
        if value is None:
            missing.append(feature)
        elif isinstance(value, str) and not value.strip():
            missing.append(feature)
        elif isinstance(value, float) and math.isnan(value):
            missing.append(feature)

    return missing


def serialize_document(document):
    if not document:
        return document

    result = dict(document)

    for key, value in list(result.items()):
        if isinstance(value, ObjectId):
            result[key] = str(value)

    if "_id" in result:
        result["_id"] = str(result["_id"])

    return result


def get_supported_emergency_match(value):
    if not isinstance(value, str):
        return None

    value = value.strip().casefold()

    for emergency in get_supported_emergencies() or []:
        if str(emergency).strip().casefold() == value:
            return emergency

    return None


def save_triage_result(
    session_id,
    emergency_type,
    patient_data,
    result,
    source,
):
    missing_features = get_missing_features(patient_data)

    record = {
        "session_id": session_id,
        "emergency_type": emergency_type,
        "patient_data": patient_data,
        "triage": result,
        "created_at": utc_now(),
        "source": source,
        "missing_features": missing_features,
    }

    inserted = triage_collection.insert_one(record)

    return str(inserted.inserted_id), missing_features


def initialize_demo_ambulances():
    """
    Insert demo ambulances only when they do not exist.
    Preserve existing ambulance records and statuses.
    """
    demo_ambulances = [
        {
            "ambulance_id": "AMB-101",
            "vehicle": "Basic Life Support",
            "status": "Available",
            "contact": "Available",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
        {
            "ambulance_id": "AMB-102",
            "vehicle": "Advanced Life Support",
            "status": "Available",
            "contact": "Available",
            "latitude": 12.9750,
            "longitude": 77.6000,
        },
        {
            "ambulance_id": "AMB-103",
            "vehicle": "Emergency Response Unit",
            "status": "Available",
            "contact": "Available",
            "latitude": 12.9650,
            "longitude": 77.5800,
        },
    ]

    for ambulance in demo_ambulances:
        ambulance["created_at"] = utc_now()
        ambulance["updated_at"] = utc_now()

        ambulances_collection.update_one(
            {"ambulance_id": ambulance["ambulance_id"]},
            {"$setOnInsert": ambulance},
            upsert=True,
        )

    print("SmartEMS demo ambulance initialization completed.")


def initialize_dispatch_indexes():
    """
    Enforce one active dispatch per ambulance and one active
    dispatch per session ID.

    Existing duplicate active records must be reviewed before
    these indexes can be created.
    """
    dispatch_collection.create_index(
        [("ambulance_id", 1)],
        unique=True,
        partialFilterExpression={
            "status": ACTIVE_STATUS,
        },
        name="one_active_dispatch_per_ambulance",
    )

    dispatch_collection.create_index(
        [("session_id", 1)],
        unique=True,
        partialFilterExpression={
            "status": ACTIVE_STATUS,
            "session_id": {"$type": "string"},
        },
        name="one_active_dispatch_per_session",
    )

    print("SmartEMS dispatch indexes initialized.")


def reserve_available_ambulance(exclude_ambulance_id=None):
    """Atomically reserve an Available ambulance."""
    query = {
        "status": {
            "$regex": "^Available$",
            "$options": "i",
        }
    }

    if exclude_ambulance_id:
        query["ambulance_id"] = {"$ne": exclude_ambulance_id}

    return ambulances_collection.find_one_and_update(
        query,
        {
            "$set": {
                "status": ACTIVE_STATUS,
                "updated_at": utc_now(),
            }
        },
        sort=[("ambulance_id", 1)],
        return_document=ReturnDocument.AFTER,
    )


def active_dispatch_exists(ambulance_id):
    return dispatch_collection.find_one({
        "ambulance_id": ambulance_id,
        "status": {
            "$regex": "^En Route$",
            "$options": "i",
        },
    }) is not None


def release_ambulance_if_unused(ambulance_id):
    """
    Release an ambulance only if no active dispatch uses it.
    """
    if not ambulance_id:
        return

    if active_dispatch_exists(ambulance_id):
        return

    ambulances_collection.update_one(
        {
            "ambulance_id": ambulance_id,
            "status": {
                "$regex": "^En Route$",
                "$options": "i",
            },
        },
        {
            "$set": {
                "status": "Available",
                "updated_at": utc_now(),
            }
        },
    )


def reconcile_ambulance_statuses():
    """
    Synchronize ambulance availability with active dispatches.
    Run at startup to correct stale En Route statuses.
    """
    active_dispatches = list(
        dispatch_collection.find(
            {
                "status": {
                    "$regex": "^En Route$",
                    "$options": "i",
                }
            },
            {"_id": 0, "ambulance_id": 1},
        )
    )

    active_ambulance_ids = {
        item.get("ambulance_id")
        for item in active_dispatches
        if item.get("ambulance_id")
    }

    # Release ambulances marked En Route without an active dispatch.
    stale_ambulances = ambulances_collection.find(
        {
            "status": {
                "$regex": "^En Route$",
                "$options": "i",
            }
        },
        {"_id": 0, "ambulance_id": 1},
    )

    for ambulance in stale_ambulances:
        ambulance_id = ambulance.get("ambulance_id")

        if (
            ambulance_id
            and ambulance_id not in active_ambulance_ids
        ):
            ambulances_collection.update_one(
                {
                    "ambulance_id": ambulance_id,
                    "status": {
                        "$regex": "^En Route$",
                        "$options": "i",
                    },
                },
                {
                    "$set": {
                        "status": "Available",
                        "updated_at": utc_now(),
                    }
                },
            )

    # Ensure every ambulance with an active dispatch is En Route.
    for ambulance_id in active_ambulance_ids:
        ambulances_collection.update_one(
            {"ambulance_id": ambulance_id},
            {
                "$set": {
                    "status": ACTIVE_STATUS,
                    "updated_at": utc_now(),
                }
            },
        )

    print("SmartEMS ambulance status reconciliation completed.")


def existing_dispatch_response(dispatch):
    """Return the existing active dispatch for a repeated request."""
    ambulance = ambulances_collection.find_one(
        {"ambulance_id": dispatch.get("ambulance_id")},
        {"_id": 0},
    )

    return jsonify({
        "success": True,
        "emergency_id": dispatch.get("emergency_id"),
        "dispatch_id": str(dispatch["_id"]),
        "priority": dispatch.get("priority"),
        "ambulance": serialize_document(ambulance),
        "message": "An active dispatch already exists for this session.",
    }), 200


# =========================================================
# HOME AND PREDICTION
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "SmartEMS backend is running.",
    }), 200


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    try:
        result = predict_triage(data)

        return jsonify({
            "success": True,
            "triage": result,
        }), 200

    except Exception:
        app.logger.exception("Prediction failed")

        return jsonify({
            "success": False,
            "message": "Unable to generate a triage prediction.",
        }), 500


@app.route("/api/emergency", methods=["POST"])
def create_emergency():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    patient_data = data.get("patient_data", data)

    if not isinstance(patient_data, dict):
        return jsonify({
            "success": False,
            "message": "patient_data must be a JSON object.",
        }), 400

    try:
        result = predict_triage(patient_data)

        return jsonify({
            "success": True,
            "triage": result,
        }), 200

    except Exception:
        app.logger.exception("Emergency prediction failed")

        return jsonify({
            "success": False,
            "message": "Unable to process the emergency.",
        }), 500


@app.route("/api/questions/<emergency_type>", methods=["GET"])
def emergency_questions(emergency_type):
    canonical_type = get_supported_emergency_match(emergency_type)

    if not canonical_type:
        return jsonify({
            "success": False,
            "message": "Unsupported emergency type.",
            "supported_emergencies": get_supported_emergencies(),
        }), 400

    try:
        questions = get_questions(canonical_type)

        return jsonify({
            "success": True,
            "emergency_type": canonical_type,
            "questions": questions,
        }), 200

    except Exception:
        app.logger.exception("Question retrieval failed")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve triage questions.",
        }), 500


# =========================================================
# USER: DASHBOARD PROFILE AND EMERGENCY HISTORY
# =========================================================

@app.route("/api/user/dashboard", methods=["GET"])
def user_dashboard():
    user, error = get_current_user()

    if error or not user:
        return jsonify({
            "success": False,
            "message": "Please log in to view your dashboard.",
        }), 401

    if user.get("role") != "user":
        return jsonify({
            "success": False,
            "message": "This endpoint is for user accounts only.",
        }), 403

    try:
        user_id = str(user["_id"])

        emergencies = list(
            emergencies_collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(50)
        )

        active_count = sum(
            1 for item in emergencies
            if str(item.get("status", "")).casefold() == "active"
        )

        history = []

        for document in emergencies:
            item = serialize_document(document)
            item["emergency_id"] = item.pop("_id", None)

            created_at = item.get("created_at")

            if isinstance(created_at, datetime):
                item["created_at"] = created_at.isoformat()

            history.append(item)

        return jsonify({
            "success": True,
            "profile": {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "phone": user.get("phone", ""),
            },
            "statistics": {
                "total_emergencies": len(emergencies),
                "active_emergencies": active_count,
            },
            "emergencies": history,
        }), 200

    except Exception:
        app.logger.exception("User dashboard retrieval failed")

        return jsonify({
            "success": False,
            "message": "Unable to load your dashboard.",
        }), 500


# =========================================================
# STANDARD TRIAGE
# =========================================================

@app.route("/api/triage/start", methods=["POST"])
def start_triage():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    emergency_type = get_supported_emergency_match(
        data.get("emergency_type")
    )

    if not emergency_type:
        return jsonify({
            "success": False,
            "message": "A supported emergency_type is required.",
            "supported_emergencies": get_supported_emergencies(),
        }), 400

    try:
        questions = get_questions(emergency_type)

        if not questions:
            return jsonify({
                "success": False,
                "message": "No questions are configured for this emergency.",
            }), 400

        session_id = str(uuid.uuid4())
        session = TriageSession(emergency_type)
        sessions[session_id] = session

        return jsonify({
            "success": True,
            "session_id": session_id,
            "emergency_type": emergency_type,
            "question": session.get_current_question(),
            "complete": session.is_complete(),
        }), 200

    except Exception:
        app.logger.exception("Unable to start triage")

        return jsonify({
            "success": False,
            "message": "Unable to start the triage session.",
        }), 500


# =========================================================
# ADAPTIVE TEXT / VOICE-TRANSCRIPT TRIAGE
# =========================================================

@app.route("/api/triage/adaptive/start", methods=["POST"])
def adaptive_triage_start():
    session_id = None

    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "message": "A valid JSON object is required.",
            }), 400

        description = data.get("description", "")

        if not isinstance(description, str) or not description.strip():
            return jsonify({
                "success": False,
                "message": "Please describe the emergency.",
            }), 400

        description = description.strip()

        detected_type = identify_emergency_type(description)
        emergency_type = get_supported_emergency_match(detected_type)

        if not emergency_type:
            return jsonify({
                "success": False,
                "message": (
                    "Unable to identify a supported emergency. "
                    "Please describe what happened more clearly."
                ),
                "supported_emergencies": get_supported_emergencies(),
            }), 400

        questions = get_questions(emergency_type)

        if not questions:
            return jsonify({
                "success": False,
                "message": "No questions are configured for this emergency.",
            }), 400

        extracted_answers = extract_known_answers(
            description,
            questions,
        )

        session_id = str(uuid.uuid4())

        session = TriageSession(
            emergency_type,
            initial_answers=extracted_answers,
            adaptive=True,
        )

        sessions[session_id] = session

        # Preserve the current adaptive-flow behavior.
        patient_data = build_patient_data(
            emergency_type,
            session.get_result_data(),
        )

        if not isinstance(patient_data, dict) or not patient_data:
            sessions.pop(session_id, None)

            return jsonify({
                "success": False,
                "message": "Unable to prepare patient data.",
            }), 500

        patient_data["emergency_type"] = emergency_type

        triage_result = predict_triage(patient_data)

        if (
            not isinstance(triage_result, dict)
            or not triage_result.get("prediction")
        ):
            sessions.pop(session_id, None)

            return jsonify({
                "success": False,
                "message": "The ML model did not return a valid prediction.",
            }), 500

        triage_id, missing_features = save_triage_result(
            session_id,
            emergency_type,
            patient_data,
            triage_result,
            source="adaptive_voice_text",
        )

        return jsonify({
            "success": True,
            "complete": True,
            "session_id": session_id,
            "triage_id": triage_id,
            "emergency_type": emergency_type,
            "extracted_answers": extracted_answers,
            "patient_data": patient_data,
            "missing_features": missing_features,
            "triage": triage_result,
            "message": (
                "Triage prediction completed using the available "
                "description. Some patient details may be missing."
            ),
        }), 200

    except Exception:
        if session_id:
            sessions.pop(session_id, None)

        app.logger.exception("Adaptive triage start failed")

        return jsonify({
            "success": False,
            "message": (
                "Unable to complete adaptive triage. "
                "Check the model's handling of missing input values."
            ),
        }), 500


# =========================================================
# AMBULANCE DISPATCH
# =========================================================

@app.route("/api/ambulance/dispatch", methods=["POST"])
def dispatch_ambulance():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    triage = data.get("triage")
    patient_data = data.get("patient_data", {})

    if not isinstance(triage, dict) or not triage.get("prediction"):
        return jsonify({
            "success": False,
            "message": "A valid triage result with a prediction is required.",
        }), 400

    if not isinstance(patient_data, dict):
        return jsonify({
            "success": False,
            "message": "patient_data must be a JSON object.",
        }), 400

    session_id = data.get("session_id")

    if session_id is not None and not isinstance(session_id, str):
        return jsonify({
            "success": False,
            "message": "session_id must be a string.",
        }), 400

    if isinstance(session_id, str):
        session_id = session_id.strip() or None

    # Associate the request with the authenticated user when a token
    # is provided. Requests without a token retain the previous behavior.
    current_user = None

    if request.headers.get("Authorization"):
        current_user, auth_error = get_current_user()

        if auth_error or not current_user:
            return jsonify({
                "success": False,
                "message": "Your login session is invalid. Please log in again.",
            }), 401

        if current_user.get("role") != "user":
            return jsonify({
                "success": False,
                "message": "A user account is required to request an ambulance.",
            }), 403

    owner_id = str(current_user["_id"]) if current_user else None

    # Return the existing active dispatch for a repeated session request.
    if session_id:
        existing_dispatch = dispatch_collection.find_one({
            "session_id": session_id,
            "status": ACTIVE_STATUS,
        })

        if existing_dispatch:
            return existing_dispatch_response(existing_dispatch)

    ambulance = None
    emergency_object_id = None
    dispatch_object_id = None

    try:
        ambulance = reserve_available_ambulance()

        if not ambulance:
            return jsonify({
                "success": False,
                "message": (
                    "No ambulance is currently available. "
                    "Contact emergency services directly if immediate "
                    "help is needed."
                ),
            }), 409

        emergency_record = {
            "user_id": owner_id,
            "session_id": session_id,
            "emergency_type": (
                patient_data.get("emergency_type")
                or data.get("emergency_type")
                or "Emergency Request"
            ),
            "patient_data": patient_data,
            "triage": triage,
            "ambulance_id": ambulance["ambulance_id"],
            "status": "Active",
            "created_at": utc_now(),
        }

        emergency_result = emergencies_collection.insert_one(
            emergency_record
        )
        emergency_object_id = emergency_result.inserted_id

        dispatch_record = {
            "emergency_id": str(emergency_object_id),
            "user_id": owner_id,
            "session_id": session_id,
            "ambulance_id": ambulance["ambulance_id"],
            "priority": triage["prediction"],
            "status": ACTIVE_STATUS,
            "created_at": utc_now(),
        }

        dispatch_result = dispatch_collection.insert_one(dispatch_record)
        dispatch_object_id = dispatch_result.inserted_id

        return jsonify({
            "success": True,
            "emergency_id": str(emergency_object_id),
            "dispatch_id": str(dispatch_object_id),
            "priority": triage["prediction"],
            "ambulance": serialize_document(ambulance),
            "message": "Ambulance dispatched successfully.",
        }), 201

    except Exception as error:
        app.logger.exception("Ambulance dispatch failed")

        # Roll back only records created by this request.
        if dispatch_object_id is not None:
            dispatch_collection.delete_one({"_id": dispatch_object_id})

        if emergency_object_id is not None:
            emergencies_collection.delete_one({"_id": emergency_object_id})

        if ambulance:
            release_ambulance_if_unused(ambulance.get("ambulance_id"))

        # Handle a concurrent request that created the active dispatch first.
        if isinstance(error, DuplicateKeyError):
            if session_id:
                existing_dispatch = dispatch_collection.find_one({
                    "session_id": session_id,
                    "status": ACTIVE_STATUS,
                })

                if existing_dispatch:
                    return existing_dispatch_response(existing_dispatch)

            return jsonify({
                "success": False,
                "message": (
                    "An active dispatch conflicts with this request. "
                    "Please refresh and try again."
                ),
            }), 409

        return jsonify({
            "success": False,
            "message": "Unable to complete ambulance dispatch.",
        }), 500


# =========================================================
# AMBULANCE STATUS
# =========================================================

@app.route("/api/ambulance/status/<ambulance_id>", methods=["GET"])
def ambulance_status(ambulance_id):
    try:
        ambulance = ambulances_collection.find_one(
            {"ambulance_id": ambulance_id},
            {"_id": 0},
        )

        if not ambulance:
            return jsonify({
                "success": False,
                "message": "Ambulance not found.",
            }), 404

        return jsonify({
            "success": True,
            "ambulance": ambulance,
        }), 200

    except Exception:
        app.logger.exception("Unable to retrieve ambulance status")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve ambulance status.",
        }), 500


# =========================================================
# ADMIN: AMBULANCES
# =========================================================

@app.route("/api/admin/ambulances", methods=["GET"])
def admin_ambulances():
    try:
        ambulances = list(
            ambulances_collection.find(
                {},
                {"_id": 0},
            ).sort("ambulance_id", 1)
        )

        available_count = sum(
            1 for item in ambulances
            if str(item.get("status", "")).casefold() == "available"
        )

        return jsonify({
            "success": True,
            "active_ambulances": ambulances,
            "total_ambulances": len(ambulances),
            "available_ambulances": available_count,
        }), 200

    except Exception:
        app.logger.exception("Admin ambulance retrieval failed")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve ambulances.",
        }), 500


# =========================================================
# ADMIN: EMERGENCIES
# =========================================================

@app.route("/api/admin/emergencies", methods=["GET"])
def admin_emergencies():
    try:
        documents = list(
            emergencies_collection.find({}).sort("created_at", -1)
        )

        emergencies = []
        active_count = 0

        for document in documents:
            item = serialize_document(document)
            item["emergency_id"] = item.pop("_id", None)

            if str(item.get("status", "")).casefold() == "active":
                active_count += 1

            emergencies.append(item)

        return jsonify({
            "success": True,
            "emergencies": emergencies,
            "total_emergencies": len(emergencies),
            "active_emergencies": active_count,
        }), 200

    except Exception:
        app.logger.exception("Admin emergency retrieval failed")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve emergencies.",
        }), 500


# =========================================================
# ADMIN: DISPATCHES
# =========================================================

@app.route("/api/admin/dispatches", methods=["GET"])
def admin_dispatches():
    try:
        documents = list(
            dispatch_collection.find({}).sort("created_at", -1)
        )

        dispatches = []

        for document in documents:
            item = serialize_document(document)
            item["dispatch_id"] = item.pop("_id", None)

            if item.get("emergency_id") is not None:
                item["emergency_id"] = str(item["emergency_id"])

            dispatches.append(item)

        return jsonify({
            "success": True,
            "dispatches": dispatches,
            "total_dispatches": len(dispatches),
        }), 200

    except Exception:
        app.logger.exception("Admin dispatch retrieval failed")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve dispatches.",
        }), 500


# =========================================================
# ADMIN: REALLOCATE AMBULANCE
# =========================================================

@app.route("/api/admin/reallocate", methods=["POST"])
def reallocate_ambulance():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    dispatch_id = data.get("dispatch_id")

    if not dispatch_id or not ObjectId.is_valid(str(dispatch_id)):
        return jsonify({
            "success": False,
            "message": "A valid dispatch_id is required.",
        }), 400

    dispatch_object_id = ObjectId(str(dispatch_id))
    dispatch = dispatch_collection.find_one({"_id": dispatch_object_id})

    if not dispatch:
        return jsonify({
            "success": False,
            "message": "Dispatch not found.",
        }), 404

    if str(dispatch.get("status", "")).casefold() != "en route":
        return jsonify({
            "success": False,
            "message": "Only En Route dispatches can be reallocated.",
        }), 409

    old_ambulance_id = dispatch.get("ambulance_id")
    emergency_id = dispatch.get("emergency_id")

    if not old_ambulance_id:
        return jsonify({
            "success": False,
            "message": "The dispatch has no assigned ambulance.",
        }), 409

    if not emergency_id or not ObjectId.is_valid(str(emergency_id)):
        return jsonify({
            "success": False,
            "message": "The dispatch has an invalid emergency reference.",
        }), 409

    emergency_object_id = ObjectId(str(emergency_id))
    emergency = emergencies_collection.find_one({"_id": emergency_object_id})

    if not emergency:
        return jsonify({
            "success": False,
            "message": "The linked emergency was not found.",
        }), 404

    old_ambulance = ambulances_collection.find_one({
        "ambulance_id": old_ambulance_id
    })

    if not old_ambulance:
        return jsonify({
            "success": False,
            "message": "The assigned ambulance was not found.",
        }), 404

    replacement = None
    dispatch_updated = False
    emergency_updated = False

    try:
        replacement = reserve_available_ambulance(
            exclude_ambulance_id=old_ambulance_id
        )

        if not replacement:
            return jsonify({
                "success": False,
                "message": "No replacement ambulance is currently available.",
            }), 409

        replacement_id = replacement["ambulance_id"]

        result = dispatch_collection.update_one(
            {
                "_id": dispatch_object_id,
                "status": {
                    "$regex": "^En Route$",
                    "$options": "i",
                },
                "ambulance_id": old_ambulance_id,
            },
            {
                "$set": {
                    "ambulance_id": replacement_id,
                    "previous_ambulance_id": old_ambulance_id,
                    "reallocated_at": utc_now(),
                }
            },
        )

        if result.modified_count != 1:
            raise RuntimeError(
                "Dispatch changed before reallocation could finish."
            )

        dispatch_updated = True

        result = emergencies_collection.update_one(
            {
                "_id": emergency_object_id,
                "ambulance_id": old_ambulance_id,
            },
            {
                "$set": {
                    "ambulance_id": replacement_id,
                    "updated_at": utc_now(),
                }
            },
        )

        if result.modified_count != 1:
            raise RuntimeError(
                "The linked emergency assignment could not be updated."
            )

        emergency_updated = True

        release_ambulance_if_unused(old_ambulance_id)

        return jsonify({
            "success": True,
            "dispatch_id": str(dispatch_object_id),
            "previous_ambulance_id": old_ambulance_id,
            "ambulance": serialize_document(replacement),
            "message": "Ambulance reallocated successfully.",
        }), 200

    except Exception:
        app.logger.exception("Ambulance reallocation failed")

        if emergency_updated:
            emergencies_collection.update_one(
                {"_id": emergency_object_id},
                {
                    "$set": {
                        "ambulance_id": old_ambulance_id,
                        "updated_at": utc_now(),
                    }
                },
            )

        if dispatch_updated:
            dispatch_collection.update_one(
                {"_id": dispatch_object_id},
                {
                    "$set": {
                        "ambulance_id": old_ambulance_id,
                    },
                    "$unset": {
                        "previous_ambulance_id": "",
                        "reallocated_at": "",
                    },
                },
            )

        if replacement:
            release_ambulance_if_unused(replacement.get("ambulance_id"))

        release_ambulance_if_unused(old_ambulance_id)

        return jsonify({
            "success": False,
            "message": "Unable to reallocate the ambulance.",
        }), 500


# =========================================================
# ADMIN: RESOLVE EMERGENCY
# =========================================================

@app.route("/api/admin/resolve-emergency", methods=["POST"])
def resolve_emergency():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "A valid JSON object is required.",
        }), 400

    emergency_id = data.get("emergency_id")

    if not emergency_id or not ObjectId.is_valid(str(emergency_id)):
        return jsonify({
            "success": False,
            "message": "A valid emergency_id is required.",
        }), 400

    emergency_object_id = ObjectId(str(emergency_id))
    emergency = emergencies_collection.find_one({"_id": emergency_object_id})

    if not emergency:
        return jsonify({
            "success": False,
            "message": "Emergency not found.",
        }), 404

    if str(emergency.get("status", "")).casefold() != "active":
        return jsonify({
            "success": False,
            "message": "This emergency is not active.",
        }), 409

    ambulance_id = emergency.get("ambulance_id")

    try:
        dispatch = dispatch_collection.find_one({
            "emergency_id": str(emergency_object_id),
            "status": {
                "$regex": "^En Route$",
                "$options": "i",
            },
        })

        if not dispatch:
            return jsonify({
                "success": False,
                "message": (
                    "No active dispatch was found for this emergency. "
                    "The emergency was not changed."
                ),
            }), 409

        dispatch_result = dispatch_collection.update_one(
            {
                "_id": dispatch["_id"],
                "status": {
                    "$regex": "^En Route$",
                    "$options": "i",
                },
            },
            {
                "$set": {
                    "status": "Completed",
                    "completed_at": utc_now(),
                }
            },
        )

        if dispatch_result.modified_count != 1:
            return jsonify({
                "success": False,
                "message": "The dispatch changed. Refresh and try again.",
            }), 409

        emergency_result = emergencies_collection.update_one(
            {
                "_id": emergency_object_id,
                "status": {
                    "$regex": "^Active$",
                    "$options": "i",
                },
            },
            {
                "$set": {
                    "status": "Resolved",
                    "resolved_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )

        if emergency_result.modified_count != 1:
            dispatch_collection.update_one(
                {
                    "_id": dispatch["_id"],
                    "status": "Completed",
                },
                {
                    "$set": {
                        "status": ACTIVE_STATUS,
                    },
                    "$unset": {
                        "completed_at": "",
                    },
                },
            )

            return jsonify({
                "success": False,
                "message": (
                    "The emergency changed before resolution. "
                    "Refresh and try again."
                ),
            }), 409

        release_ambulance_if_unused(ambulance_id)

        return jsonify({
            "success": True,
            "emergency_id": str(emergency_object_id),
            "dispatch_id": str(dispatch["_id"]),
            "ambulance_id": ambulance_id,
            "message": "Emergency resolved and dispatch completed.",
        }), 200

    except Exception:
        app.logger.exception("Emergency resolution failed")

        return jsonify({
            "success": False,
            "message": "Unable to resolve the emergency.",
        }), 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    try:
        initialize_demo_ambulances()
        reconcile_ambulance_statuses()
        initialize_dispatch_indexes()

    except Exception:
        app.logger.exception(
            "SmartEMS startup initialization failed. "
            "Check MongoDB and existing active dispatch records."
        )
        raise

    print("SmartEMS backend starting...")
    print("Backend URL: http://127.0.0.1:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
