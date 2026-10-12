from mongodb import hospitals_collection

# Demo hospital records for SmartEMS.
# These are sample records, not verified live hospital data.

hospitals = [
    {
        "hospital_id": "HOSP-101",
        "name": "Demo General Hospital",
        "address": "Bengaluru, Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "available": True,
        "specialties": ["Emergency Care", "Trauma Care"]
    },
    {
        "hospital_id": "HOSP-102",
        "name": "Demo Trauma Care Centre",
        "address": "Bengaluru, Karnataka",
        "latitude": 12.9750,
        "longitude": 77.6000,
        "available": True,
        "specialties": ["Emergency Care", "Trauma Care"]
    },
    {
        "hospital_id": "HOSP-103",
        "name": "Demo Emergency Hospital",
        "address": "Bengaluru, Karnataka",
        "latitude": 12.9650,
        "longitude": 77.6100,
        "available": True,
        "specialties": ["Emergency Care"]
    }
]

for hospital in hospitals:
    hospitals_collection.update_one(
        {"hospital_id": hospital["hospital_id"]},
        {"$setOnInsert": hospital},
        upsert=True
    )

print("Demo hospital records added successfully!")
print("Total hospital records:", hospitals_collection.count_documents({}))
