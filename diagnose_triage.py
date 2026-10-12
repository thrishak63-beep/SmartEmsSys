import os
import joblib

BASE_DIR = os.path.join(
    os.path.dirname(__file__),
    "triage_ml_package_FINAL (1)"
)

model = joblib.load(os.path.join(BASE_DIR, "final_lightgbm.pkl"))
preprocessor = joblib.load(os.path.join(BASE_DIR, "preprocessor.pkl"))
classes = joblib.load(os.path.join(BASE_DIR, "classes.pkl"))
features = joblib.load(os.path.join(BASE_DIR, "model_features.pkl"))

print("\n========== MODEL DIAGNOSTICS ==========")

print("\nModel type:", type(model).__name__)
print("Model classes_:", getattr(model, "classes_", "Unavailable"))
print("Saved classes.pkl:", classes)
print("Number of model features:", len(features))
print("Feature order:", features)

print("\n========== PREPROCESSOR ==========")
print("Preprocessor type:", type(preprocessor).__name__)

if hasattr(preprocessor, "transformers_"):
    for name, transformer, columns in preprocessor.transformers_:
        print(f"\nTransformer: {name}")
        print("Input columns:", columns)
        print("Transformer type:", type(transformer).__name__)

        if hasattr(transformer, "categories_"):
            print("Categories:", transformer.categories_)

        if hasattr(transformer, "named_steps"):
            for step_name, step in transformer.named_steps.items():
                print("  Step:", step_name, type(step).__name__)

                if hasattr(step, "categories_"):
                    print("  Categories:", step.categories_)

print("\n========== DIAGNOSTICS COMPLETE ==========")