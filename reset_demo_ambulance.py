
from datetime import datetime, timezone
from mongodb import ambulances_collection

result = ambulances_collection.update_one(
    {"ambulance_id": "AMB-101"},
    {
        "$set": {
            "status": "Available",
            "updated_at": datetime.now(timezone.utc),
        }
    },
)

print("Matched:", result.matched_count)
print("Modified:", result.modified_count)

for ambulance in ambulances_collection.find(
    {},
    {"_id": 0, "ambulance_id": 1, "status": 1},
).sort("ambulance_id", 1):
    print(ambulance)
