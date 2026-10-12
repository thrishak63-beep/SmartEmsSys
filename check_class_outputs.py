
import joblib
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent / "triage_ml_package_FINAL (1)"

model = joblib.load(BASE / "final_lightgbm.pkl")
preprocessor = joblib.load(BASE / "preprocessor.pkl")
features = joblib.load(BASE / "model_features.pkl")
classes = list(model.classes_)

# Use categories that exist in the fitted encoder.
categories = preprocessor.named_transformers_["cat"].named_steps[
    "onehot"
].categories_

categorical_features = [f for f in features if f != "age"]
valid_values = {
    feature: list(values)
    for feature, values in zip(categorical_features, categories)
}

# Vary one input at a time while keeping other features missing.
tests = [
    ("Road Accident", "breathing", "Normal"),
    ("Road Accident", "breathing", "Abnormal"),
    ("Road Accident", "breathing", "Absent"),
    ("Road Accident", "conscious", "Yes"),
    ("Road Accident", "conscious", "No"),
    ("Road Accident", "accident_level", "Minor"),
    ("Road Accident", "accident_level", "Severe"),
    ("Heart Attack", "chest_pain", "Mild"),
    ("Heart Attack", "chest_pain", "Severe"),
    ("Stroke", "face_drooping", "No"),
    ("Stroke", "face_drooping", "Yes"),
    ("Drowning", "cpr_required", "No"),
    ("Drowning", "cpr_required", "Yes"),
]

print("Software diagnostic only — not clinical validation.")
print("\nEmergency | Changed feature | Value | Prediction | Probabilities")

for emergency, feature, value in tests:
    patient = {name: None for name in features}
    patient["age"] = 30
    patient["emergency_type"] = emergency
    patient[feature] = value

    # Keep all non-null categorical values inside fitted categories.
    invalid = [
        name for name in categorical_features
        if patient[name] is not None
        and patient[name] not in valid_values[name]
    ]
    if invalid:
        print("Skipped invalid input:", invalid)
        continue

    df = pd.DataFrame([patient], columns=features)
    transformed = preprocessor.transform(df)
    prediction = model.predict(transformed)[0]
    probabilities = model.predict_proba(transformed)[0]

    summary = ", ".join(
        f"{label}={prob * 100:.2f}%"
        for label, prob in zip(classes, probabilities)
    )
    print(
        f"{emergency} | {feature} | {value} | "
        f"{prediction} | {summary}"
    )

print("\nDiagnostic complete.")
id="q0m8s"
