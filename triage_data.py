from triage_normalizer import normalize_answer


MODEL_FEATURES = [
    "age",
    "emergency_type",
    "incident_location",
    "bleeding",
    "conscious",
    "breathing",
    "accident_level",
    "visible_fracture",
    "trapped",
    "injury_type",
    "pain_level",
    "chest_pain",
    "sweating",
    "shortness_of_breath",
    "face_drooping",
    "arm_weakness",
    "speech_difficulty",
    "poison_type",
    "vomiting",
    "seizures",
    "entry_exit_burn",
    "muscle_spasm",
    "fall_after_shock",
    "water_type",
    "water_inhalation",
    "cpr_required",
    "fall_height",
    "head_injury",
    "animal_type",
    "bite_location",
    "venomous",
    "weapon_involved",
    "injury_location",
    "visible_injury"
]


def build_patient_data(emergency_type, answers, age=30):

    patient_data = {}

    # Start with missing values
    for feature in MODEL_FEATURES:
        patient_data[feature] = None

    # Required values
    patient_data["age"] = age
    patient_data["emergency_type"] = emergency_type

    # Add and normalize answers
    for feature, value in answers.items():

        if feature in patient_data:
            patient_data[feature] = normalize_answer(
                feature,
                value
            )

    return patient_data