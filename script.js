
const API_BASE_URL = "http://127.0.0.1:5000";
function getElement(id) {
    return document.getElementById(id);
}
function setButtonDisabled(id, disabled) {
    const button = document.getElementById(id);

    if (button) {
        button.disabled = disabled;
    }
}
function setAdaptiveStatus(message) {
    const statusElement = document.getElementById("adaptiveStatus");

    if (statusElement) {
        statusElement.textContent = message;
    }
}
function setText(elementId, message) {
    const element = document.getElementById(elementId);

    if (element) {
        element.textContent = message;
    }
}
function saveTriageAndPatientData(result, sessionId) {
    if (!result || !result.triage || !result.patient_data) {
        throw new Error("Triage or patient data is missing.");
    }

    localStorage.setItem("triageResult", JSON.stringify(result.triage));
    localStorage.setItem("patientData", JSON.stringify(result.patient_data));

    if (sessionId) {
        localStorage.setItem("triageSessionId", sessionId);
    }
}
let adaptiveSessionId = null;
let recognition = null;
let isListening = false;
let adaptiveRequestInProgress = false;
let sosRequestInProgress = false;

// --------------------------------------------------
// COMMON API HELPERS
// --------------------------------------------------

async function readApiResponse(response) {
    let result;

    try {
        result = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok || result.success === false) {
        throw new Error(
            result.message ||
            result.error ||
            `Request failed (${response.status}).`
        );
    }

    return result;
}


async function apiPost(endpoint, data) {
    const headers = {
        "Content-Type": "application/json"
    };

    const token = localStorage.getItem("smartemsToken");

    // Attach the logged-in user's token when available.
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers,
        body: JSON.stringify(data)
    });

    return readApiResponse(response);
}
// --------------------------------------------------
// AMBULANCE DISPATCH AND TRACKING
// --------------------------------------------------

async function dispatchAndTrack(
    result,
    sessionId,
    statusElementId = "adaptiveStatus"
) {
    if (!result || !result.triage || !result.patient_data) {
        throw new Error("Cannot dispatch without a completed triage result.");
    }

    saveTriageAndPatientData(result, sessionId);

    setText(statusElementId, "Assigning an available ambulance...");

    const dispatchResult = await apiPost(
        "/api/ambulance/dispatch",
        {
            session_id: sessionId,
            patient_data: result.patient_data,
            triage: result.triage
        }
    );

    if (dispatchResult.success === false) {
        throw new Error(
            dispatchResult.message || "Ambulance dispatch failed."
        );
    }

    if (dispatchResult.ambulance) {
        localStorage.setItem(
            "ambulanceData",
            JSON.stringify(dispatchResult.ambulance)
        );
    }

    if (dispatchResult.emergency_id) {
        localStorage.setItem(
            "emergencyId",
            dispatchResult.emergency_id
        );
    }

    if (dispatchResult.dispatch_id) {
        localStorage.setItem(
            "dispatchId",
            dispatchResult.dispatch_id
        );
    }

    setText(statusElementId, "Ambulance assigned. Opening tracking...");

    window.location.href = "tracking.html";
}

// --------------------------------------------------
// EXISTING SOS FLOW
// --------------------------------------------------

async function startSOSFlow() {
    if (sosRequestInProgress) {
        return;
    }

    const emergencyType = prompt(
        "Select your emergency type:\n\n" +
        "1. Road Accident\n" +
        "2. Heart Attack\n" +
        "3. Stroke\n" +
        "4. Poisoning\n" +
        "5. Electric Shock\n" +
        "6. Drowning\n" +
        "7. Fracture\n" +
        "8. Animal Bite\n" +
        "9. Fall From Height\n" +
        "10. Weapon Injury"
    );

    if (!emergencyType || !emergencyType.trim()) {
        return;
    }

    const emergencyTypes = [
        "Road Accident",
        "Heart Attack",
        "Stroke",
        "Poisoning",
        "Electric Shock",
        "Drowning",
        "Fracture",
        "Animal Bite",
        "Fall From Height",
        "Weapon Injury"
    ];

    let selectedType = emergencyType.trim();

    if (/^\d+$/.test(selectedType)) {
        selectedType = emergencyTypes[Number(selectedType) - 1] || "";
    } else {
        selectedType = emergencyTypes.find(
            type => type.toLowerCase() === selectedType.toLowerCase()
        ) || "";
    }

    if (!selectedType) {
        alert("Please select a supported emergency type.");
        return;
    }

    sosRequestInProgress = true;
    setButtonDisabled("sosButton", true);
    setText("locationStatus", "Starting emergency triage...");

    try {
        const startResult = await apiPost("/api/triage/start", {
            emergency_type: selectedType
        });

        const sessionId = startResult.session_id;

        if (!sessionId) {
            throw new Error("The server did not create a triage session.");
        }

        let result = startResult;

        while (!result.complete) {
            const question = result.question;

            if (!question || !question.question) {
                throw new Error("The server did not provide the next question.");
            }

            const answer = prompt(question.question);

            if (answer === null) {
                setText("locationStatus", "Triage cancelled.");
                return;
            }

            result = await apiPost("/api/triage/answer", {
                session_id: sessionId,
                answer: answer.trim()
            });
        }

        if (!result.triage || !result.patient_data) {
            throw new Error("The server returned incomplete triage data.");
        }

        setText("locationStatus", "Triage complete. Dispatching ambulance...");

        await dispatchAndTrack(
            result,
            sessionId,
            "locationStatus"
        );

    } catch (error) {
        console.error("SOS flow error:", error);

        setText(
            "locationStatus",
            error.message || "Unable to complete the emergency request."
        );

        alert(
            "Emergency request could not be completed.\n\n" +
            (error.message || "Please try again.")
        );

    } finally {
        sosRequestInProgress = false;
        setButtonDisabled("sosButton", false);
    }
}

// --------------------------------------------------
// ADAPTIVE TRIAGE - TEXT AND VOICE
// --------------------------------------------------

async function startAdaptiveTriage() {
    if (adaptiveRequestInProgress) {
        return;
    }

    const descriptionElement = getElement("emergencyDescription");

    const description = descriptionElement
        ? descriptionElement.value.trim()
        : "";

    if (!description) {
        setAdaptiveStatus("Please describe the emergency first.");
        return;
    }

    adaptiveRequestInProgress = true;
    setButtonDisabled("startAdaptiveButton", true);
    setAdaptiveStatus("Understanding the emergency...");

    const questionArea = getElement("adaptiveQuestionArea");

    if (questionArea) {
        questionArea.hidden = true;
    }

    try {
        const result = await apiPost(
            "/api/triage/adaptive/start",
            {
                description: description
            }
        );

        adaptiveSessionId = result.session_id || null;

        // Backend could not identify the emergency category.
        if (result.needs_emergency_type) {
            renderEmergencyTypeQuestion(result);
            setAdaptiveStatus(
                "Please clarify the type of emergency."
            );
            return;
        }

        if (result.complete) {
            setAdaptiveStatus(
                "Triage complete. Assigning an ambulance..."
            );

            await dispatchAndTrack(
                result,
                adaptiveSessionId,
                "adaptiveStatus"
            );

            return;
        }

        if (result.question) {
            renderAdaptiveQuestion(result.question);

            setAdaptiveStatus(
                "Please answer the following essential question."
            );

            return;
        }

        throw new Error(
            result.message ||
            "The server did not return a triage question or result."
        );

    } catch (error) {
        console.error("Adaptive triage error:", error);

        setAdaptiveStatus(
            error.message || "Unable to start adaptive triage."
        );

    } finally {
        adaptiveRequestInProgress = false;
        setButtonDisabled("startAdaptiveButton", false);
    }
}

// --------------------------------------------------
// EMERGENCY TYPE CLARIFICATION
// --------------------------------------------------

function renderEmergencyTypeQuestion(result) {
    const area = getElement("adaptiveQuestionArea");
    const questionText = getElement("adaptiveQuestionText");
    const answerContainer = getElement("adaptiveAnswerContainer");

    if (!area || !questionText || !answerContainer) {
        setAdaptiveStatus(
            result.message ||
            "Please clarify the emergency type."
        );
        return;
    }

    questionText.textContent =
        result.message || "What type of emergency is this?";

    answerContainer.replaceChildren();

    const select = document.createElement("select");
    select.id = "adaptiveEmergencyType";
    select.required = true;

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select emergency type";
    select.appendChild(placeholder);

    const types = result.supported_emergencies || [
        "Road Accident",
        "Animal Bite",
        "Heart Attack",
        "Stroke",
        "Poisoning",
        "Electric Shock",
        "Drowning",
        "Fracture",
        "Weapon Injury",
        "Fall From Height"
    ];

    types.forEach(type => {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        select.appendChild(option);
    });

    answerContainer.appendChild(select);

    area.hidden = false;

    const submitButton = getElement("submitAdaptiveAnswer");

    if (submitButton) {
        submitButton.onclick = submitEmergencyType;
    }
}

async function submitEmergencyType() {
    const select = getElement("adaptiveEmergencyType");

    if (!select || !select.value) {
        setAdaptiveStatus("Please select an emergency type.");
        return;
    }

    const descriptionElement = getElement("emergencyDescription");

    const description = descriptionElement
        ? descriptionElement.value.trim()
        : "";

    // Restart adaptive triage with the selected category.
    if (descriptionElement) {
        descriptionElement.value =
            `${select.value}. ${description}`.trim();
    }

    const area = getElement("adaptiveQuestionArea");

    if (area) {
        area.hidden = true;
    }

    await startAdaptiveTriage();
}

// --------------------------------------------------
// RENDER ADAPTIVE QUESTIONS
// --------------------------------------------------

function renderAdaptiveQuestion(question) {
    const area = getElement("adaptiveQuestionArea");
    const questionText = getElement("adaptiveQuestionText");
    const answerContainer = getElement("adaptiveAnswerContainer");

    if (!area || !questionText || !answerContainer) {
        setAdaptiveStatus(
            "The question interface is unavailable. Please refresh the page."
        );
        return;
    }

    questionText.textContent = question.question || "Please clarify.";

    answerContainer.replaceChildren();

    const feature = question.feature || "";
    const options = Array.isArray(question.options)
        ? question.options
        : [];

    if (options.length > 0) {
        const select = document.createElement("select");

        select.id = "adaptiveAnswerInput";
        select.required = true;

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choose an answer";
        select.appendChild(placeholder);

        options.forEach(item => {
            const option = document.createElement("option");

            if (typeof item === "object" && item !== null) {
                option.value =
                    item.value ?? item.label ?? item.name ?? "";

                option.textContent =
                    item.label ?? item.name ?? item.value ?? "";
            } else {
                option.value = String(item);
                option.textContent = String(item);
            }

            select.appendChild(option);
        });

        answerContainer.appendChild(select);

    } else {
        const input = document.createElement("input");

        input.id = "adaptiveAnswerInput";
        input.type = "text";
        input.autocomplete = "off";
        input.placeholder = "Enter your answer";
        input.required = true;

        answerContainer.appendChild(input);
    }

    area.hidden = false;

    const submitButton = getElement("submitAdaptiveAnswer");

    if (submitButton) {
        submitButton.onclick = answerAdaptiveQuestion;
        submitButton.disabled = false;
    }

    // Speak the question when browser speech synthesis is available.
    // This is an accessibility aid, not a substitute for emergency services.
    if ("speechSynthesis" in window && question.question) {
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(
            question.question
        );

        utterance.lang = "en-IN";
        utterance.rate = 0.95;

        window.speechSynthesis.speak(utterance);
    }

    // Keep feature available for debugging if needed.
    console.debug("Adaptive question feature:", feature);
}

// --------------------------------------------------
// SUBMIT ADAPTIVE ANSWER
// --------------------------------------------------

async function answerAdaptiveQuestion() {
    if (adaptiveRequestInProgress) {
        return;
    }

    if (!adaptiveSessionId) {
        setAdaptiveStatus("No active triage session. Please start again.");
        return;
    }

    const answerElement = getElement("adaptiveAnswerInput");

    if (!answerElement || !answerElement.value.trim()) {
        setAdaptiveStatus("Please provide an answer.");
        return;
    }

    const answer = answerElement.value.trim();

    adaptiveRequestInProgress = true;
    setButtonDisabled("submitAdaptiveAnswer", true);

    setAdaptiveStatus("Processing your answer...");

    try {
        if ("speechSynthesis" in window) {
            window.speechSynthesis.cancel();
        }

        const result = await apiPost("/api/triage/answer", {
            session_id: adaptiveSessionId,
            answer: answer
        });

        if (result.complete) {
            setAdaptiveStatus(
                "Triage complete. Assigning an ambulance..."
            );

            const area = getElement("adaptiveQuestionArea");

            if (area) {
                area.hidden = true;
            }

            await dispatchAndTrack(
                result,
                adaptiveSessionId,
                "adaptiveStatus"
            );

            return;
        }

        if (result.question) {
            renderAdaptiveQuestion(result.question);

            setAdaptiveStatus(
                "Please answer the next essential question."
            );

            return;
        }

        throw new Error(
            result.message || "The server did not return the next question."
        );

    } catch (error) {
        console.error("Adaptive answer error:", error);

        setAdaptiveStatus(
            error.message || "Unable to process your answer."
        );

    } finally {
        adaptiveRequestInProgress = false;
        setButtonDisabled("submitAdaptiveAnswer", false);
    }
}

// --------------------------------------------------
// VOICE RECOGNITION
// --------------------------------------------------

function startVoiceRecognition() {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        setAdaptiveStatus(
            "Voice recognition is not supported by this browser. " +
            "Please use Chrome or enter the description by text."
        );
        return;
    }

    if (isListening) {
        return;
    }

    const descriptionElement = getElement("emergencyDescription");

    if (!descriptionElement) {
        setAdaptiveStatus("Emergency description field was not found.");
        return;
    }

    recognition = new SpeechRecognition();

    recognition.lang = "en-IN";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    let finalTranscript = "";
    let recognitionFailed = false;

    recognition.onstart = function () {
        isListening = true;

        setButtonDisabled("startVoiceButton", true);
        setButtonDisabled("stopVoiceButton", false);

        setAdaptiveStatus("Listening... Please describe the emergency.");
    };

    recognition.onresult = function (event) {
        let interimTranscript = "";

        for (
            let i = event.resultIndex;
            i < event.results.length;
            i++
        ) {
            const transcript = event.results[i][0].transcript;

            if (event.results[i].isFinal) {
                finalTranscript += transcript + " ";
            } else {
                interimTranscript += transcript;
            }
        }

        descriptionElement.value =
            `${finalTranscript} ${interimTranscript}`.trim();
    };

    recognition.onerror = function (event) {
        recognitionFailed = true;

        console.error("Speech recognition error:", event.error);

        if (event.error === "not-allowed") {
            setAdaptiveStatus(
                "Microphone permission was denied. Allow microphone access " +
                "and try again."
            );
        } else if (event.error === "no-speech") {
            setAdaptiveStatus(
                "No speech was detected. Please tap the voice button and try again."
            );
        } else {
            setAdaptiveStatus(
                "Voice recognition failed. Please try again or type the description."
            );
        }
    };

    recognition.onend = async function () {
        isListening = false;

        setButtonDisabled("startVoiceButton", false);
        setButtonDisabled("stopVoiceButton", true);

        if (recognitionFailed) {
            return;
        }

        const description = descriptionElement.value.trim();

        if (!description) {
            setAdaptiveStatus(
                "I couldn't hear the emergency clearly. Please try again."
            );
            return;
        }

        setAdaptiveStatus(
            "Voice received. Starting triage automatically..."
        );

        // Automatically start adaptive triage after the user finishes speaking.
        await startAdaptiveTriage();
    };

    try {
        recognition.start();
    } catch (error) {
        console.error("Could not start speech recognition:", error);

        isListening = false;

        setButtonDisabled("startVoiceButton", false);
        setButtonDisabled("stopVoiceButton", true);

        setAdaptiveStatus(
            "Could not start the microphone. Please try again."
        );
    }
}

function stopVoiceRecognition() {
    if (recognition && isListening) {
        recognition.stop();
        setAdaptiveStatus("Finishing voice recognition...");
    }
}

// --------------------------------------------------
// EVENT LISTENERS
// --------------------------------------------------

document.addEventListener("DOMContentLoaded", function () {
    const sosButton = getElement("sosButton");

    if (sosButton) {
        sosButton.addEventListener("click", startSOSFlow);
    }

    const startVoiceButton = getElement("startVoiceButton");

    if (startVoiceButton) {
        startVoiceButton.addEventListener(
            "click",
            startVoiceRecognition
        );
    }

    const stopVoiceButton = getElement("stopVoiceButton");

    if (stopVoiceButton) {
        stopVoiceButton.disabled = true;

        stopVoiceButton.addEventListener(
            "click",
            stopVoiceRecognition
        );
    }

    const startAdaptiveButton = getElement("startAdaptiveButton");

    if (startAdaptiveButton) {
        startAdaptiveButton.addEventListener(
            "click",
            startAdaptiveTriage
        );
    }

    const submitAdaptiveButton = getElement("submitAdaptiveAnswer");

    if (submitAdaptiveButton) {
        submitAdaptiveButton.addEventListener(
            "click",
            answerAdaptiveQuestion
        );
    }

    const answerContainer = getElement("adaptiveAnswerContainer");

    if (answerContainer) {
        answerContainer.addEventListener("keydown", function (event) {
            if (
                event.key === "Enter" &&
                event.target.id === "adaptiveAnswerInput"
            ) {
                event.preventDefault();
                answerAdaptiveQuestion();
            }
        });
    }

    console.log("SmartEMS script initialized.");
});
