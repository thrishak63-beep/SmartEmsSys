import pandas as pd

from triage_model import (
    model,
    preprocessor,
    classes,
    model_features,
)

EMERGENCY_TYPES = [
    "Animal Bite",
    "Assault",
    "Burn Injury",
    "Drowning",
    "Electric Shock",
    "Fall From Height",
    "Heart Attack",
    "Poisoning",
    "Road Accident",
    "Stroke",
]

print("\n========== TRIAGE BASELINE TEST ==========")

for emergency_type in EMERGENCY_TYPES:
    patient_data = {
        feature: None for feature in model_features
    }

    patient_data["age"] = 30
    patient_data["emergency_type"] = emergency_type

    df = pd.DataFrame([patient_data])[model_features]

    processed_data = preprocessor.transform(df)

    prediction = model.predict(processed_data)[0]
    probabilities = model.predict_proba(processed_data)[0]

    probability_dict = {
        str(classes[i]): round(
            float(probabilities[i]) * 100, 2
        )
        for i in range(len(classes))
    }

    print(f"\nEmergency: {emergency_type}")
    print("Prediction:", prediction)
    print("Probabilities:", probability_dict)

print("\n========== TEST COMPLETE ==========")