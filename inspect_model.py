
import joblib
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "triage_ml_package_FINAL (1)"

model = joblib.load(MODEL_DIR / "final_lightgbm.pkl")
preprocessor = joblib.load(MODEL_DIR / "preprocessor.pkl")

print("=== ENCODED FEATURE IMPORTANCE ===")

try:
    transformed_names = preprocessor.get_feature_names_out()
    importances = model.feature_importances_

    print("Encoded feature count:", len(transformed_names))
    print("Importance count:", len(importances))

    ranked = sorted(
        zip(transformed_names, importances),
        key=lambda item: item[1],
        reverse=True
    )

    for name, score in ranked[:25]:
        print(f"{name}: {score}")

except Exception as exc:
    print("Could not retrieve encoded feature names:", exc)

print("\n=== MODEL CLASS DISTRIBUTION ===")
print("Classes:", list(model.classes_))

print("\nInspection complete.")
id="r8jgkn"
