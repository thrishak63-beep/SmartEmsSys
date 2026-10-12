import joblib
import pandas as pd
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "triage_ml_package_FINAL (1)"

model = joblib.load(MODEL_DIR / "final_lightgbm.pkl")
preprocessor = joblib.load(MODEL_DIR / "preprocessor.pkl")
classes = joblib.load(MODEL_DIR / "classes.pkl")
model_features = joblib.load(MODEL_DIR / "model_features.pkl")


def make_patient(profile):
    patient = {feature: None for feature in model_features}
    patient.update({
        "age": 35,
        "emergency_type": "Road Accident",
        "incident_location": "Road"
    })
    patient.update(profile)
    return pd.DataFrame([patient], columns=model_features)


def test_profile(name, profile):
    patient_df = make_patient(profile)
    processed = preprocessor.transform(patient_df)

    prediction = model.predict(processed)[0]
    probabilities = model.predict_proba(processed)[0]

    print(f"\n--- {name} ---")
    print("Prediction:", prediction)

    for class_name, probability in zip(classes, probabilities):
        print(f"{class_name}: {probability * 100:.2f}%")


# Synthetic inputs for checking model behavior only.
profile_a = {
    "conscious": "Yes",
    "breathing": "Normal",
    "bleeding": None,
    "accident_level": "Minor",
    "visible_fracture": "No",
    "trapped": "No",
    "injury_type": "Limb Injury",
    "pain_level": "Mild",
    "head_injury": "No",
    "injury_location": "Leg",
    "visible_injury": "No"
}

profile_b = {
    "conscious": "No",
    "breathing": "Absent",
    "bleeding": "Severe",
    "accident_level": "Severe",
    "visible_fracture": "Yes",
    "trapped": "Yes",
    "injury_type": "Multiple Injuries",
    "pain_level": "Severe",
    "head_injury": "Yes",
    "injury_location": "Multiple Areas",
    "visible_injury": "Yes"
}

print("SmartEMS model behavior diagnostic")
test_profile("Profile A", profile_a)
test_profile("Profile B", profile_b)

print("\nDiagnostic complete. Predictions are not clinical advice.")

