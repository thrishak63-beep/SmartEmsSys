import os
import joblib
import pandas as pd


# ML package location
BASE_DIR = os.path.join(
    os.path.dirname(__file__),
    "triage_ml_package_FINAL (1)"
)

MODEL_PATH = os.path.join(BASE_DIR, "final_lightgbm.pkl")
PREPROCESSOR_PATH = os.path.join(BASE_DIR, "preprocessor.pkl")
CLASSES_PATH = os.path.join(BASE_DIR, "classes.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "model_features.pkl")


# Load ML files
model = joblib.load(MODEL_PATH)
preprocessor = joblib.load(PREPROCESSOR_PATH)
classes = joblib.load(CLASSES_PATH)
model_features = joblib.load(FEATURES_PATH)


def predict_triage(patient_data):
    """
    Takes patient data as a dictionary
    and returns the ML triage prediction.
    """

    # Create DataFrame
    df = pd.DataFrame([patient_data])

    # Ensure correct feature order
    df = df[model_features]

    # Preprocess
    processed_data = preprocessor.transform(df)

    # Prediction
    prediction = model.predict(processed_data)[0]

    # Probabilities
    probabilities = model.predict_proba(processed_data)[0]

    probability_dict = {
        str(classes[i]): round(float(probabilities[i]) * 100, 2)
        for i in range(len(classes))
    }

    return {
        "prediction": str(prediction),
        "probabilities": probability_dict
    }


if __name__ == "__main__":
    print("✅ SmartEMS triage model loaded successfully!")
    print("Model:", type(model))
    print("Features:", len(model_features))