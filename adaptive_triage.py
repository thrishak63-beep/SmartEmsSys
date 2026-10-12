
import re

from triage_questions import get_supported_emergencies


EMERGENCY_RULES = [
    ("Road Accident", [
        r"\broad accident\b", r"\bcar crash\b", r"\bcar accident\b",
        r"\bbike accident\b", r"\bvehicle collision\b", r"\broad crash\b",
        r"\bhit by (a )?car\b", r"\btraffic accident\b",
        r"\broad collision\b", r"\bvehicle accident\b",
    ]),
    ("Animal Bite", [
        r"\banimal bite\b", r"\bdog bite\b", r"\bcat bite\b",
        r"\bsnake bite\b", r"\bbitten by (a )?(dog|cat|snake|animal)\b",
    ]),
    ("Heart Attack", [
        r"\bheart attack\b", r"\bcardiac emergency\b",
        r"\bsuspected cardiac\b", r"\bheart pain\b",
    ]),
    ("Stroke", [
        r"\bstroke\b", r"\bface drooping\b", r"\bslurred speech\b",
        r"\bsudden one[- ]sided weakness\b",
    ]),
    ("Poisoning", [
        r"\bpoisoning\b", r"\bswallowed poison\b",
        r"\bswallowed a chemical\b", r"\bchemical ingestion\b",
        r"\bpoison\b", r"\bingested a toxic substance\b",
    ]),
    ("Electric Shock", [
        r"\belectric shock\b", r"\belectrical shock\b",
        r"\belectrocuted\b", r"\belectricity shocked\b",
        r"\bshocked by electricity\b",
    ]),
    ("Drowning", [
        r"\bdrowning\b", r"\bnear drowning\b",
        r"\bpulled from (the )?(water|pool|river|sea)\b",
        r"\bwater inhalation\b", r"\bsubmerged in water\b",
    ]),
    ("Fall From Height", [
        r"\bfall from (a )?height\b",
        r"\bfell from (a )?(roof|balcony|ladder|building|tree)\b",
        r"\bfell off (a )?(roof|balcony|ladder|building|tree)\b",
        r"\bfell from a height\b",
    ]),
    ("Burn Injury", [
        r"\bburn injury\b", r"\bburned\b", r"\bburnt\b",
        r"\bscalded\b", r"\bsevere burn\b", r"\bskin burns?\b",
    ]),
    ("Assault", [
        r"\bassault\b", r"\battacked\b", r"\bstabbed\b",
        r"\bweapon injury\b", r"\binjured with a (knife|weapon)\b",
        r"\bshot with a weapon\b",
    ]),
]


def _normalise(text):
    """Normalize text without discarding medically relevant negations."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def identify_emergency_type(description):
    """Identify a supported emergency category from explicit wording."""
    if not isinstance(description, str) or not description.strip():
        return None

    text = _normalise(description)
    supported = get_supported_emergencies() or []

    lookup = {
        str(item).strip().lower(): str(item).strip()
        for item in supported
    }

    # Prefer an explicitly stated supported category.
    for item in supported:
        name = str(item).strip()
        if name and re.search(
            r"\b" + re.escape(name.lower()) + r"\b", text
        ):
            return name

    for category, patterns in EMERGENCY_RULES:
        canonical = lookup.get(category.lower())
        if canonical and any(
            re.search(pattern, text) for pattern in patterns
        ):
            return canonical

    return None


def _option_details(option):
    if isinstance(option, dict):
        value = option.get("value")
        label = option.get("label") or option.get("text") or value or ""
        return value if value is not None else label, str(label)

    return option, str(option)


def _match_option(options, keywords):
    """Match a meaning to a real option without inventing a model value."""
    normalized_keywords = [
        str(keyword).strip().lower()
        for keyword in keywords
        if str(keyword).strip()
    ]

    # Exact matches first.
    for option in options or []:
        value, label = _option_details(option)
        if label.strip().lower() in normalized_keywords:
            return value

    # Then allow a keyword to match a longer option label.
    for option in options or []:
        value, label = _option_details(option)
        normalized = label.strip().lower()

        if any(
            keyword in normalized
            for keyword in normalized_keywords
            if len(keyword) >= 4
        ):
            return value

    return None


def _match_yes_no(options, yes):
    """Return Yes/No only when the question actually offers that choice."""
    if yes:
        return _match_option(options, ["yes", "true"])
    return _match_option(options, ["no", "false"])


def _yes_no_answer(feature, text, options):
    """Extract explicit binary features, handling negation."""
    patterns = {
        "conscious": (
            [
                r"\bunconscious\b", r"\bunresponsive\b",
                r"\bnot responding\b", r"\bnot conscious\b",
                r"\bdoes not respond\b", r"\bnot awake\b",
            ],
            [
                r"\bconscious\b", r"\bawake\b", r"\balert\b",
                r"\bresponding normally\b", r"\bfully responsive\b",
            ],
        ),
        "visible_fracture": (
            [
                r"\bno visible fracture\b", r"\bno fracture\b",
                r"\bwithout a fracture\b",
            ],
            [
                r"\bvisible fracture\b", r"\bfractured\b",
                r"\bfracture\b", r"\bbroken bone\b",
            ],
        ),
        "trapped": (
            [r"\bnot trapped\b", r"\bnot stuck\b", r"\bfreed from\b"],
            [
                r"\btrapped\b", r"\bstuck inside\b",
                r"\bunable to get out\b", r"\bcannot get out\b",
                r"\bcan't get out\b", r"\btrapped under\b",
            ],
        ),
        "head_injury": (
            [r"\bno head injury\b", r"\bno head wound\b"],
            [
                r"\bhead injury\b", r"\bhit (their |his |her )?head\b",
                r"\binjured (their |his |her )?head\b",
                r"\bhead wound\b", r"\bhead trauma\b",
            ],
        ),
        "visible_injury": (
            [r"\bno visible injuries?\b", r"\bno injury visible\b"],
            [
                r"\bvisible injuries?\b", r"\bvisible wound\b",
                r"\bopen wound\b", r"\bbleeding wound\b",
            ],
        ),
        "sweating": (
            [r"\bnot sweating\b", r"\bno sweating\b"],
            [r"\bsweating\b", r"\bcold sweat\b", r"\bclammy skin\b"],
        ),
        "shortness_of_breath": (
            [
                r"\bno shortness of breath\b",
                r"\bno breathing difficulty\b",
                r"\bnot short of breath\b",
                r"\bbreathing without difficulty\b",
            ],
            [
                r"\bshortness of breath\b", r"\bshort of breath\b",
                r"\bdifficulty breathing\b",
                r"\bstruggling to breathe\b",
                r"\bbreathless\b", r"\bcan't catch (their )?breath\b",
            ],
        ),
        "face_drooping": (
            [
                r"\bno face drooping\b",
                r"\bface is not drooping\b",
                r"\bface is normal\b",
            ],
            [
                r"\bface drooping\b", r"\bdrooping face\b",
                r"\bone side of (the )?face droops\b",
                r"\bfacial droop\b",
            ],
        ),
        "arm_weakness": (
            [r"\bno arm weakness\b", r"\barms are not weak\b"],
            [
                r"\barm weakness\b",
                r"\bweakness in (the )?(left|right|one) arm\b",
                r"\bcannot lift (the )?(left|right|one) arm\b",
                r"\bcan't lift (the )?(left|right|one) arm\b",
            ],
        ),
        "speech_difficulty": (
            [
                r"\bno speech difficulty\b", r"\bspeech is normal\b",
                r"\bspeaking normally\b",
            ],
            [
                r"\bspeech difficulty\b", r"\bslurred speech\b",
                r"\bdifficulty speaking\b", r"\bcannot speak clearly\b",
                r"\bcan't speak clearly\b",
            ],
        ),
        "vomiting": (
            [
                r"\bnot vomiting\b", r"\bno vomiting\b",
                r"\bhas not vomited\b",
            ],
            [r"\bvomiting\b", r"\bvomited\b", r"\bthrowing up\b"],
        ),
        "seizures": (
            [r"\bno seizures\b", r"\bnot having a seizure\b"],
            [r"\bseizure\b", r"\bseizures\b", r"\bconvulsions\b"],
        ),
        "entry_exit_burn": (
            [
                r"\bno entry or exit burn\b", r"\bno burn marks\b",
                r"\bno visible burn marks\b",
            ],
            [
                r"\bentry and exit burn\b", r"\bentry burn\b",
                r"\bexit burn\b", r"\bburn marks\b",
            ],
        ),
        "muscle_spasm": (
            [r"\bno muscle spasms?\b", r"\bno muscle twitching\b"],
            [r"\bmuscle spasms?\b", r"\bmuscle twitching\b"],
        ),
        "fall_after_shock": (
            [
                r"\bdid not fall after the shock\b",
                r"\bno fall after the shock\b",
            ],
            [
                r"\bfell after the shock\b",
                r"\bfell following the shock\b",
            ],
        ),
        "water_inhalation": (
            [r"\bno water inhalation\b", r"\bdid not inhale water\b"],
            [r"\binhaled water\b", r"\bwater inhalation\b"],
        ),
        "cpr_required": (
            [r"\bcpr not required\b", r"\bno cpr needed\b"],
            [
                r"\bcpr required\b", r"\bneeds cpr\b",
                r"\bneeds cardiopulmonary resuscitation\b",
            ],
        ),
    }

    if feature not in patterns:
        return None

    negative_patterns, positive_patterns = patterns[feature]
    masked_text = text
    negative_match = False

    for pattern in negative_patterns:
        matches = list(re.finditer(pattern, masked_text))
        if matches:
            negative_match = True
            for match in reversed(matches):
                masked_text = (
                    masked_text[:match.start()]
                    + " " * (match.end() - match.start())
                    + masked_text[match.end():]
                )

    positive_match = any(
        re.search(pattern, masked_text)
        for pattern in positive_patterns
    )

    if negative_match and positive_match:
        return None

    if negative_match:
        return _match_yes_no(options, False)

    if positive_match:
        return _match_yes_no(options, True)

    return None


def _extract_bleeding(text, options):
    """Extract bleeding only when the configured options support it."""
    if re.search(
        r"\b(no bleeding|not bleeding|without bleeding)\b",
        text,
    ):
        return _match_option(options, ["none", "no bleeding", "no"])

    if re.search(
        r"\b(severe|heavy|uncontrolled|profuse)\s+bleeding\b"
        r"|\bbleeding (is |was )?(severe|heavy|uncontrolled|profuse)\b"
        r"|\bbleeding heavily\b",
        text,
    ):
        answer = _match_option(options, ["severe", "heavy"])
        if answer is not None:
            return answer

    if re.search(
        r"\b(minor|mild|light|slight)\s+bleeding\b"
        r"|\bbleeding (is |was )?(minor|mild|light|slight)\b",
        text,
    ):
        answer = _match_option(options, ["minor", "mild", "light"])
        if answer is not None:
            return answer

    # Do not infer severity from the word "bleeding" alone.
    if re.search(r"\bbleeding\b", text):
        return _match_option(options, ["yes", "present"])

    return None


def _extract_severity(feature, text, options):
    """Extract severity only when the description states it clearly."""
    if feature not in {"pain_level", "chest_pain"}:
        return None

    if feature == "chest_pain":
        if re.search(
            r"\b(severe|intense|extreme)\s+chest pain\b"
            r"|\bchest pain (is |was )?(severe|intense|extreme)\b",
            text,
        ):
            return _match_option(options, ["severe", "intense", "extreme"])

        if re.search(
            r"\bmoderate\s+chest pain\b"
            r"|\bchest pain (is |was )?moderate\b",
            text,
        ):
            return _match_option(options, ["moderate"])

        if re.search(
            r"\b(mild|slight)\s+chest pain\b"
            r"|\bchest pain (is |was )?(mild|slight)\b",
            text,
        ):
            return _match_option(options, ["mild", "slight"])

        if re.search(r"\b(no chest pain|without chest pain)\b", text):
            return _match_option(options, ["none", "no", "no chest pain"])

        return None

    if re.search(
        r"\b(severe|intense|extreme) pain\b"
        r"|\bpain (is |was )?(severe|intense|extreme)\b",
        text,
    ):
        return _match_option(options, ["severe", "intense", "extreme"])

    if re.search(r"\bmoderate pain\b|\bpain (is |was )?moderate\b", text):
        return _match_option(options, ["moderate"])

    if re.search(
        r"\b(mild|slight) pain\b|\bpain (is |was )?(mild|slight)\b",
        text,
    ):
        return _match_option(options, ["mild", "slight"])

    if re.search(r"\b(no pain|without pain)\b", text):
        return _match_option(options, ["none", "no pain", "no"])

    return None


def _extract_breathing(text, options):
    """Map explicit breathing descriptions to available categories."""
    if re.search(
        r"\b(not breathing|no breathing|stopped breathing|"
        r"has stopped breathing|isn't breathing)\b",
        text,
    ):
        return _match_option(options, ["absent", "not breathing"])

    if re.search(
        r"\b(breathing abnormally|abnormal breathing|"
        r"breathing with difficulty|struggling to breathe|"
        r"difficulty breathing|difficulty in breathing|"
        r"laboured breathing|labored breathing|breathless)\b",
        text,
    ):
        return _match_option(options, ["abnormal", "difficulty"])

    if re.search(
        r"\b(breathing normally|normal breathing|"
        r"breathing clearly|breathing without difficulty|"
        r"no breathing difficulty)\b",
        text,
    ):
        return _match_option(options, ["normal"])

    return None


def _extract_accident_level(text, options):
    if re.search(
        r"\b(severe|major|high[- ]severity)\s+"
        r"(road\s+)?(accident|collision|crash)\b"
        r"|\b(accident|collision|crash) (is |was )?"
        r"(severe|major)\b",
        text,
    ):
        return _match_option(options, ["severe", "major"])

    if re.search(
        r"\b(minor|mild|low[- ]severity)\s+"
        r"(road\s+)?(accident|collision|crash)\b"
        r"|\b(accident|collision|crash) (is |was )?minor\b",
        text,
    ):
        return _match_option(options, ["minor", "mild"])

    return None


def _extract_categorical_answer(feature, text, options):
    """Match explicitly mentioned option labels for selected text features."""
    supported_features = {
        "injury_type",
        "injury_location",
        "animal_type",
        "bite_location",
        "poison_type",
        "water_type",
        "fall_height",
        "weapon_involved",
    }

    if feature not in supported_features:
        return None

    generic_labels = {
        "unknown", "other", "none", "yes", "no",
        "severe", "minor", "mild", "moderate",
    }

    for option in options or []:
        value, label = _option_details(option)
        label_text = label.strip().lower()

        if label_text in generic_labels or len(label_text) < 4:
            continue

        pattern = r"\b" + re.escape(label_text) + r"\b"

        if re.search(pattern, text):
            return value

    return None


def extract_known_answers(description, questions):
    """
    Extract only clearly stated answers from the description.

    Ambiguous or unmentioned details remain unanswered so the
    adaptive session can ask an appropriate follow-up question.
    """
    if not isinstance(description, str) or not description.strip():
        return {}

    text = _normalise(description)
    extracted = {}

    for question in questions or []:
        feature = question.get("feature")
        options = question.get("options", [])

        if not feature:
            continue

        if feature == "accident_level":
            answer = _extract_accident_level(text, options)

        elif feature == "breathing":
            answer = _extract_breathing(text, options)

        elif feature == "bleeding":
            answer = _extract_bleeding(text, options)

        elif feature in {"pain_level", "chest_pain"}:
            answer = _extract_severity(feature, text, options)

        else:
            answer = _yes_no_answer(feature, text, options)

        if answer is None:
            answer = _extract_categorical_answer(feature, text, options)

        if answer is not None:
            extracted[feature] = answer

    return extracted
