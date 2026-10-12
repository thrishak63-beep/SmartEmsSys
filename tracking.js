console.log("SmartEMS Tracking initialized");

document.addEventListener("DOMContentLoaded", function () {
    const API_BASE_URL = "http://127.0.0.1:5000";

    function readStorage(key) {
        try {
            return JSON.parse(localStorage.getItem(key) || "null");
        } catch (error) {
            console.error("Storage read error:", key, error);
            return null;
        }
    }

    const triage = readStorage("triageResult");
    const ambulance = readStorage("ambulanceData");

    // -----------------------------------------------------
    // TRIAGE RESULT
    // -----------------------------------------------------

    const prediction = document.getElementById("triagePrediction");
    const critical = document.getElementById("criticalProbability");
    const urgent = document.getElementById("urgentProbability");
    const nonUrgent = document.getElementById("nonUrgentProbability");

    if (triage) {
        if (prediction) {
            prediction.textContent = triage.prediction || "Unavailable";
        }

        const probabilities = triage.probabilities || {};

        if (critical) {
            critical.textContent = `${probabilities.Critical ?? 0}%`;
        }

        if (urgent) {
            urgent.textContent = `${probabilities.Urgent ?? 0}%`;
        }

        if (nonUrgent) {
            nonUrgent.textContent =
                `${probabilities["Non-Urgent"] ?? 0}%`;
        }
    } else if (prediction) {
        prediction.textContent = "Triage data unavailable";
    }

    // -----------------------------------------------------
    // AMBULANCE DETAILS
    // -----------------------------------------------------

    const ambulanceId = document.getElementById("ambulanceId");
    const vehicle = document.getElementById("ambulanceVehicle");
    const status = document.getElementById("ambulanceStatus");
    const contact = document.getElementById("ambulanceContact");

    if (ambulance) {
        if (ambulanceId) {
            ambulanceId.textContent =
                ambulance.ambulance_id || ambulance.id || "Not available";
        }

        if (vehicle) {
            vehicle.textContent =
                ambulance.vehicle ||
                ambulance.vehicle_type ||
                "Not available";
        }

        if (status) {
            status.textContent = ambulance.status || "Assigned";
        }

        if (contact) {
            contact.textContent = ambulance.contact || "Not available";
        }
    } else {
        [ambulanceId, vehicle, status, contact].forEach(function (element) {
            if (element) element.textContent = "Not available";
        });

        console.warn("No ambulance data found.");
    }

    console.log("Tracking triage:", triage);
    console.log("Tracking ambulance:", ambulance);

    // -----------------------------------------------------
    // HOSPITAL DESTINATION
    // -----------------------------------------------------

    async function loadHospitalDestination() {
        const destinationCard = Array.from(
            document.querySelectorAll(".tracking-card")
        ).find(function (card) {
            const label = card.querySelector(".card-label");

            return label &&
                label.textContent.trim().toUpperCase() === "DESTINATION";
        });

        if (!destinationCard) {
            console.warn("Hospital destination card not found.");
            return;
        }

        const heading = destinationCard.querySelector("h2");
        const description =
            destinationCard.querySelector(".hospital-description");
        const hospitalStatus =
            destinationCard.querySelector(".hospital-status");

        function showHospitalMessage(message) {
            if (heading) heading.textContent = "Hospital Information";
            if (description) description.textContent = message;
            if (hospitalStatus) hospitalStatus.textContent = message;
        }

        const dispatchId = localStorage.getItem("dispatchId");

        if (!dispatchId) {
            showHospitalMessage(
                "No saved dispatch ID was found. Start a new emergency dispatch to load its destination."
            );
            return;
        }

        try {
            if (description) {
                description.textContent = "Loading assigned hospital...";
            }

            const response = await fetch(
                `${API_BASE_URL}/api/dispatch/${encodeURIComponent(dispatchId)}/hospital`
            );

            const result = await response.json();

            if (!response.ok || !result.success || !result.hospital) {
                throw new Error(
                    result.message || "Hospital destination is unavailable."
                );
            }

            const hospital = result.hospital;

            if (heading) {
                heading.textContent =
                    hospital.name || "Hospital name unavailable";
            }

            if (description) {
                description.textContent =
                    hospital.address || "Hospital address unavailable";
            }

            if (hospitalStatus) {
                const distance = Number(hospital.distance_km_demo);

                hospitalStatus.textContent =
                    `Hospital ID: ${hospital.hospital_id || "Unavailable"}` +
                    (
                        Number.isFinite(distance)
                            ? ` • Approx. ${distance.toFixed(2)} km from ambulance`
                            : ""
                    ) +
                    " • Demo distance, not road distance";
            }

            const hospitalLabel =
                document.querySelector(".hospital-label");

            if (hospitalLabel) {
                hospitalLabel.textContent =
                    hospital.name || "Hospital";
            }

            console.log("Assigned hospital:", hospital);

        } catch (error) {
            console.error("Hospital destination loading failed:", error);

            showHospitalMessage(
                error.message ||
                "Unable to load the assigned hospital. Please check the backend."
            );
        }
    }

    // Load the destination independently of the demo map animation.
    loadHospitalDestination();

    // -----------------------------------------------------
    // DEMO MAP MOVEMENT
    // -----------------------------------------------------

    const map = document.querySelector(".tracking-map");
    const ambulanceMarker = document.querySelector(".ambulance-marker");
    const hospitalMarker = document.querySelector(".hospital-marker");
    const locationUpdate = document.getElementById("locationUpdate");

    if (!map || !ambulanceMarker || !hospitalMarker) {
        console.error("Tracking map or required markers not found.");

        if (locationUpdate) {
            locationUpdate.textContent = "Map markers unavailable";
        }

        return;
    }

    if (!ambulance) {
        if (locationUpdate) {
            locationUpdate.textContent =
                "Ambulance data unavailable; demo movement not started";
        }
        return;
    }

    const startLat = Number(ambulance.latitude);
    const startLng = Number(ambulance.longitude);

    if (!Number.isFinite(startLat) || !Number.isFinite(startLng)) {
        console.warn("Ambulance coordinates are missing or invalid.");

        if (locationUpdate) {
            locationUpdate.textContent = "Demo coordinates unavailable";
        }

        return;
    }

    if (window.smartemsTrackingInterval) {
        clearInterval(window.smartemsTrackingInterval);
        window.smartemsTrackingInterval = null;
    }

    if (getComputedStyle(map).position === "static") {
        map.style.position = "relative";
    }

    function getMarkerPosition(marker) {
        const mapRect = map.getBoundingClientRect();
        const markerRect = marker.getBoundingClientRect();

        return {
            x: markerRect.left + markerRect.width / 2 - mapRect.left,
            y: markerRect.top + markerRect.height / 2 - mapRect.top
        };
    }

    const mapRect = map.getBoundingClientRect();

    if (mapRect.width === 0 || mapRect.height === 0) {
        console.error("The tracking map has no visible dimensions.");
        return;
    }

    const start = getMarkerPosition(ambulanceMarker);
    const destination = getMarkerPosition(hospitalMarker);

    const startX = (start.x / mapRect.width) * 100;
    const startY = (start.y / mapRect.height) * 100;
    const endX = (destination.x / mapRect.width) * 100;
    const endY = (destination.y / mapRect.height) * 100;

    ambulanceMarker.style.position = "absolute";
    ambulanceMarker.style.left = `${startX}%`;
    ambulanceMarker.style.top = `${startY}%`;
    ambulanceMarker.style.right = "auto";
    ambulanceMarker.style.bottom = "auto";
    ambulanceMarker.style.transform = "translate(-50%, -50%)";
    ambulanceMarker.style.zIndex = "10";
    ambulanceMarker.style.display = "block";
    ambulanceMarker.style.transition =
        "left 0.3s linear, top 0.3s linear";

    const totalSteps = 60;
    const intervalMs = 300;
    let step = 0;

    if (locationUpdate) {
        locationUpdate.textContent =
            `Demo movement • Starting coordinates: ` +
            `${startLat.toFixed(5)}, ${startLng.toFixed(5)}`;
    }

    function moveTowardHospital() {
        step++;

        const progress = Math.min(step / totalSteps, 1);

        const currentX = startX + (endX - startX) * progress;
        const currentY = startY + (endY - startY) * progress;

        ambulanceMarker.style.left = `${currentX}%`;
        ambulanceMarker.style.top = `${currentY}%`;

        // Illustrative values only; no GPS connection.
        const currentLat = startLat + (0.001 * progress);
        const currentLng = startLng + (0.001 * progress);

        if (locationUpdate) {
            locationUpdate.textContent =
                `Demo movement • ${currentLat.toFixed(6)}, ` +
                `${currentLng.toFixed(6)}`;
        }

        if (progress >= 1) {
            clearInterval(window.smartemsTrackingInterval);
            window.smartemsTrackingInterval = null;

            if (locationUpdate) {
                locationUpdate.textContent =
                    "Demo animation completed; actual arrival is unconfirmed";
            }

            console.log(
                "Demo animation completed; no real arrival was confirmed."
            );
            return;
        }

        console.log("Simulated ambulance movement:", {
            progress: `${Math.round(progress * 100)}%`,
            latitude: currentLat,
            longitude: currentLng
        });
    }

    window.smartemsTrackingInterval = setInterval(
        moveTowardHospital,
        intervalMs
    );

    console.log("Simulated ambulance-to-hospital movement started.");
});
