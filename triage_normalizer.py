
NORMALIZATIONS = {
    "bleeding": {
        "None": None,
        "No bleeding": None,
        "Mild": "Minor",
        "Minor": "Minor",
        "Severe": "Severe",
    },
    "pain_level": {
        "None": None,
        "Mild": "Mild",
        "Moderate": "Moderate",
        "Severe": "Severe",
    },
    "chest_pain": {
        "None": None,
        "No": None,
        "Mild": "Mild",
        "Moderate": "Moderate",
        "Severe": "Severe",
    },
    "water_type": {
        "Other": None,
        "None": None,
    },
    "fall_height": {
        "Medium (2-5 m)": "Medium (2-5 m)",
        "Moderate (2-5 m)": "Medium (2-5 m)",
        "None": None,
    },
    "bite_location": {
        "Other": None,
        "None": None,
    },
    "venomous": {
        "Unknown": None,
    },
    "weapon_involved": {
        "Yes": None,
        "No": None,
        "Sharp Object": "Sharp Object",
        "Other Weapon": "Other Weapon",
    },
    "injury_type": {
        "Multiple": "Multiple Injuries",
    },
    "injury_location": {
        "Abdomen": None,
        "Multiple": "Multiple Areas",
        "Multiple Areas": "Multiple Areas",
    },
}


def normalize_answer(feature, value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()

        if not value or value.lower() in {"nan", "null"}:
            return None

        # Preserve the model's existing feature-specific mappings.
        mappings = NORMALIZATIONS.get(feature, {})

        for original, normalized in mappings.items():
            if value.casefold() == original.casefold():
                return normalized

        # Canonicalize common yes/no responses.
        if value.casefold() == "yes":
            return "Yes"

        if value.casefold() == "no":
            return "No"

    return value
