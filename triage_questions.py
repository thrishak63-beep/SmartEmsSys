import os
import json

BASE_DIR = os.path.join(
    os.path.dirname(__file__),
    "triage_ml_package_FINAL (1)"
)

QUESTION_FILE = os.path.join(
    BASE_DIR,
    "QUESTION_SETS.json"
)

with open(QUESTION_FILE, "r", encoding="utf-8") as file:
    QUESTION_SETS = json.load(file)


def get_questions(emergency_type):
    questions = QUESTION_SETS.get(emergency_type)

    if questions is None:
        return []

    result = []

    for question in questions:
        feature_name = question[0]
        question_text = question[1]
        options = question[2]

        result.append({
            "feature": feature_name,
            "question": question_text,
            "options": options
        })

    return result


def get_supported_emergencies():
    return list(QUESTION_SETS.keys())


if __name__ == "__main__":
    print("✅ QUESTION_SETS loaded successfully!")

    print("\nSupported emergency types:")

    for emergency in get_supported_emergencies():
        print("-", emergency)

    print("\nRoad Accident questions:")

    questions = get_questions("Road Accident")

    for question in questions:
        print(
            f"{question['feature']}: "
            f"{question['question']}"
        )