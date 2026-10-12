from math import radians, sin, cos, sqrt, atan2
from datetime import datetime

from bson import ObjectId
from flask import Blueprint, jsonify

from mongodb import (
    hospitals_collection,
    ambulances_collection,
    dispatch_collection,
    emergencies_collection,
)

hospital_bp = Blueprint("hospital_service", __name__)


def utc_now():
    return datetime.utcnow()


def distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def select_nearest_hospital(ambulance):
    try:
        ambulance_lat = float(ambulance["latitude"])
        ambulance_lon = float(ambulance["longitude"])
    except (KeyError, TypeError, ValueError):
        return None

    hospitals = hospitals_collection.find({"available": True})
    candidates = []

    for hospital in hospitals:
        try:
            lat = float(hospital["latitude"])
            lon = float(hospital["longitude"])

            hospital["distance_km_demo"] = round(
                distance_km(ambulance_lat, ambulance_lon, lat, lon),
                2,
            )

            candidates.append((hospital["distance_km_demo"], hospital))

        except (KeyError, TypeError, ValueError):
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    hospital = candidates[0][1]

    return {
        "hospital_id": hospital.get("hospital_id"),
        "name": hospital.get("name", "Hospital name unavailable"),
        "address": hospital.get("address", "Address unavailable"),
        "latitude": hospital.get("latitude"),
        "longitude": hospital.get("longitude"),
        "available": hospital.get("available", False),
        "specialties": hospital.get("specialties", []),
        "distance_km_demo": hospital.get("distance_km_demo"),
    }


def assign_hospital(dispatch):
    """Assign once and retain the saved hospital for this dispatch."""
    existing = dispatch.get("hospital")

    if existing:
        return existing

    ambulance = ambulances_collection.find_one({
        "ambulance_id": dispatch.get("ambulance_id")
    })

    if not ambulance:
        return None

    hospital = select_nearest_hospital(ambulance)

    if not hospital:
        return None

    dispatch_id = dispatch["_id"]
    emergency_id = dispatch.get("emergency_id")

    result = dispatch_collection.update_one(
        {
            "_id": dispatch_id,
            "hospital": {"$exists": False},
        },
        {
            "$set": {
                "hospital_id": hospital["hospital_id"],
                "hospital": hospital,
                "hospital_assigned_at": utc_now(),
            }
        },
    )

    # If another request assigned the hospital concurrently,
    # use the destination that was actually saved.
    saved_dispatch = dispatch_collection.find_one({"_id": dispatch_id})
    saved_hospital = (
        saved_dispatch.get("hospital") if saved_dispatch else None
    )

    if not saved_hospital:
        return None

    if emergency_id and ObjectId.is_valid(str(emergency_id)):
        emergencies_collection.update_one(
            {"_id": ObjectId(str(emergency_id))},
            {
                "$set": {
                    "hospital_id": saved_hospital.get("hospital_id"),
                    "hospital": saved_hospital,
                    "updated_at": utc_now(),
                }
            },
        )

    return saved_hospital


@hospital_bp.route("/api/hospitals", methods=["GET"])
def list_hospitals():
    try:
        hospitals = []

        for hospital in hospitals_collection.find({"available": True}):
            hospitals.append({
                "hospital_id": hospital.get("hospital_id"),
                "name": hospital.get("name"),
                "address": hospital.get("address"),
                "latitude": hospital.get("latitude"),
                "longitude": hospital.get("longitude"),
                "available": hospital.get("available", False),
                "specialties": hospital.get("specialties", []),
            })

        return jsonify({
            "success": True,
            "hospitals": hospitals,
            "total": len(hospitals),
        }), 200

    except Exception:
        return jsonify({
            "success": False,
            "message": "Unable to retrieve hospitals.",
        }), 500


@hospital_bp.route("/api/dispatch/<dispatch_id>/hospital", methods=["GET"])
def get_dispatch_hospital(dispatch_id):
    if not ObjectId.is_valid(dispatch_id):
        return jsonify({
            "success": False,
            "message": "Invalid dispatch ID.",
        }), 400

    try:
        dispatch = dispatch_collection.find_one({
            "_id": ObjectId(dispatch_id)
        })

        if not dispatch:
            return jsonify({
                "success": False,
                "message": "Dispatch not found.",
            }), 404

        hospital = assign_hospital(dispatch)

        if not hospital:
            return jsonify({
                "success": False,
                "message": "No available hospital with valid coordinates was found.",
            }), 404

        return jsonify({
            "success": True,
            "dispatch_id": dispatch_id,
            "hospital": hospital,
        }), 200

    except Exception:
        return jsonify({
            "success": False,
            "message": "Unable to retrieve the dispatch destination.",
        }), 500
