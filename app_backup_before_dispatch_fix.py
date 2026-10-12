from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid

from triage_model import predict_triage
from triage_questions import get_questions
from triage_session import TriageSession
from triage_data import build_patient_data

from mongodb import (
    users_collection,
    emergencies_collection,
    triage_collection,
    ambulances_collection,
    hospitals_collection,
    dispatch_collection
)


app = Flask(__name__)
CORS(app)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return "SmartEMS Backend is Running!"


# =========================================================
# DIRECT PREDICTION
# =========================================================

@app.route("/predict", methods=["POST"])
def predict():

    try:
        patient_data = request.get_json()

        if not patient_data:
            return jsonify({
                "error": "No patient data received"
            }), 400

        result = predict_triage(patient_data)

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# EMERGENCY API
# =========================================================

@app.route("/api/emergency", methods=["POST"])
def emergency():

    try:
        patient_data = request.get_json()

        if not patient_data:
            return jsonify({
                "success": False,
                "error": "No emergency data received"
            }), 400

        result = predict_triage(patient_data)

        return jsonify({
            "success": True,
            "triage": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# QUESTIONS API
# =========================================================

@app.route("/api/questions/<emergency_type>", methods=["GET"])
def questions(emergency_type):

    try:
        question_list = get_questions(emergency_type)

        if not question_list:
            return jsonify({
                "success": False,
                "error": "Emergency type not found"
            }), 404

        return jsonify({
            "success": True,
            "emergency_type": emergency_type,
            "questions": question_list
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# TRIAGE SESSIONS
# =========================================================

sessions = {}


# =========================================================
# START TRIAGE
# =========================================================

@app.route("/api/triage/start", methods=["POST"])
def start_triage():

    try:
        data = request.get_json()

        if not data or "emergency_type" not in data:
            return jsonify({
                "success": False,
                "error": "Emergency type is required"
            }), 400

        emergency_type = data["emergency_type"]

        questions = get_questions(emergency_type)

        if not questions:
            return jsonify({
                "success": False,
                "error": "Unsupported emergency type"
            }), 400

        session_id = str(uuid.uuid4())

        sessions[session_id] = TriageSession(emergency_type)

        first_question = sessions[session_id].get_current_question()

        return jsonify({
            "success": True,
            "session_id": session_id,
            "emergency_type": emergency_type,
            "question": first_question
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# ANSWER TRIAGE
# =========================================================

@app.route("/api/triage/answer", methods=["POST"])
def answer_triage():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No answer data received"
            }), 400

        session_id = data.get("session_id")
        answer = data.get("answer")

        if not session_id or answer is None:
            return jsonify({
                "success": False,
                "error": "Session ID and answer are required"
            }), 400

        session = sessions.get(session_id)

        if session is None:
            return jsonify({
                "success": False,
                "error": "Invalid session ID"
            }), 404

        session.answer_question(answer)

        # =====================================================
        # TRIAGE COMPLETE
        # =====================================================

        if session.is_complete():

            answers = session.get_result_data()

            patient_data = build_patient_data(
                session.emergency_type,
                answers
            )

            result = predict_triage(patient_data)

            # =================================================
            # SAVE TRIAGE RESULT
            # =================================================

            triage_record = {
                "session_id": session_id,
                "emergency_type": session.emergency_type,
                "patient_data": patient_data,
                "triage": result,
                "created_at": datetime.utcnow()
            }

            triage_result = triage_collection.insert_one(
                triage_record
            )

            return jsonify({
                "success": True,
                "complete": True,
                "triage_id": str(triage_result.inserted_id),
                "patient_data": patient_data,
                "triage": result
            })

        # =====================================================
        # NEXT QUESTION
        # =====================================================

        next_question = session.get_current_question()

        return jsonify({
            "success": True,
            "complete": False,
            "question": next_question
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# AMBULANCE DISPATCH
# =========================================================

@app.route("/api/ambulance/dispatch", methods=["POST"])
def dispatch_ambulance():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No dispatch data received"
            }), 400

        triage = data.get("triage")
        patient_data = data.get("patient_data", {})
        session_id = data.get("session_id")

        if not triage:
            return jsonify({
                "success": False,
                "error": "Triage result is required"
            }), 400

        prediction = triage.get("prediction")

        if not prediction:
            return jsonify({
                "success": False,
                "error": "Triage prediction is missing"
            }), 400

        # =====================================================
        # AMBULANCE
        # =====================================================

        ambulance = {
            "ambulance_id": "AMB-104",
            "vehicle": "Emergency Response Unit",
            "status": "En Route",
            "contact": "Available",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "updated_at": datetime.utcnow()
        }

        # =====================================================
        # SAVE / UPDATE AMBULANCE
        # =====================================================

        ambulances_collection.update_one(
            {
                "ambulance_id": ambulance["ambulance_id"]
            },
            {
                "$set": ambulance
            },
            upsert=True
        )

        # =====================================================
        # SAVE EMERGENCY
        # =====================================================

        emergency_record = {
            "session_id": session_id,
            "patient_data": patient_data,
            "triage": triage,
            "ambulance_id": ambulance["ambulance_id"],
            "status": "Active",
            "created_at": datetime.utcnow()
        }

        emergency_result = emergencies_collection.insert_one(
            emergency_record
        )

        emergency_id = str(
            emergency_result.inserted_id
        )

        # =====================================================
        # SAVE DISPATCH
        # =====================================================

        dispatch_record = {
            "emergency_id": emergency_id,
            "session_id": session_id,
            "ambulance_id": ambulance["ambulance_id"],
            "priority": prediction,
            "status": "En Route",
            "created_at": datetime.utcnow()
        }

        dispatch_result = dispatch_collection.insert_one(
            dispatch_record
        )

        return jsonify({
            "success": True,
            "emergency_id": emergency_id,
            "dispatch_id": str(dispatch_result.inserted_id),
            "priority": prediction,
            "ambulance": ambulance,
            "message": "Ambulance assigned and dispatch recorded successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# AMBULANCE TRACKING
# =========================================================

@app.route(
    "/api/ambulance/status/<ambulance_id>",
    methods=["GET"]
)
def ambulance_status(ambulance_id):

    try:

        ambulance = ambulances_collection.find_one(
            {
                "ambulance_id": ambulance_id
            },
            {
                "_id": 0
            }
        )

        if not ambulance:

            return jsonify({
                "success": False,
                "error": "Ambulance not found"
            }), 404

        return jsonify({
            "success": True,
            "ambulance": ambulance
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# ADMIN — AMBULANCES
# =========================================================

@app.route("/api/admin/ambulances", methods=["GET"])
def admin_ambulances():

    try:

        ambulances = list(
            ambulances_collection.find(
                {},
                {
                    "_id": 0
                }
            )
        )

        return jsonify({
            "success": True,
            "active_ambulances": ambulances
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# ADMIN — EMERGENCIES
# =========================================================

@app.route("/api/admin/emergencies", methods=["GET"])
def admin_emergencies():

    try:

        emergencies = list(
            emergencies_collection.find(
                {},
                {
                    "_id": 0
                }
            ).sort(
                "created_at",
                -1
            )
        )

        return jsonify({
            "success": True,
            "emergencies": emergencies
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# ADMIN — DISPATCHES
# =========================================================

@app.route("/api/admin/dispatches", methods=["GET"])
def admin_dispatches():

    try:

        dispatches = list(
            dispatch_collection.find(
                {},
                {
                    "_id": 0
                }
            ).sort(
                "created_at",
                -1
            )
        )

        return jsonify({
            "success": True,
            "dispatches": dispatches
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    app.run(
        debug=True
    )