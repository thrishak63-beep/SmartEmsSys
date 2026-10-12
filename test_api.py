import requests

url = "http://127.0.0.1:5000/api/emergency"

patient = {
    "age": 35,
    "emergency_type": "Road Accident",
    "incident_location": "Road",
    "bleeding": "Severe",
    "conscious": "No",
    "breathing": "Abnormal",
    "accident_level": "Severe",
    "visible_fracture": "Yes",
    "trapped": "No",
    "injury_type": "Multiple",
    "pain_level": "Severe",
    "chest_pain": "No",
    "sweating": "No",
    "shortness_of_breath": "No",
    "face_drooping": "No",
    "arm_weakness": "No",
    "speech_difficulty": "No",
    "poison_type": "None",
    "vomiting": "No",
    "seizures": "No",
    "entry_exit_burn": "No",
    "muscle_spasm": "No",
    "fall_after_shock": "No",
    "water_type": "None",
    "water_inhalation": "No",
    "cpr_required": "No",
    "fall_height": "None",
    "head_injury": "Yes",
    "animal_type": "None",
    "bite_location": "None",
    "venomous": "No",
    "weapon_involved": "No",
    "injury_location": "Multiple",
    "visible_injury": "Yes"
}

response = requests.post(url, json=patient)

print("Status Code:", response.status_code)
print("Response:")
print(response.json())