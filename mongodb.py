from pymongo import MongoClient

MONGO_URI = "mongodb://127.0.0.1:27017/"

client = MongoClient(MONGO_URI)

db = client["smartems"]

users_collection = db["users"]
emergencies_collection = db["emergencies"]
triage_collection = db["triage_results"]
ambulances_collection = db["ambulances"]
hospitals_collection = db["hospitals"]
dispatch_collection = db["dispatches"]

print("MongoDB connected successfully!")