
/* ================= SMARTEMS ADMIN DASHBOARD ================= */

function getApiBaseUrl() {
    return typeof API_BASE_URL !== "undefined"
        ? API_BASE_URL
        : "http://127.0.0.1:5000";
}

const ADMIN_API_URL = getApiBaseUrl();

console.log("SmartEMS Admin Dashboard initialized");


/* ================= HELPERS ================= */

async function fetchAdminData(endpoint) {
    const response = await fetch(`${ADMIN_API_URL}${endpoint}`);
    const data = await response.json();

    if (!response.ok || !data.success) {
        throw new Error(
            data.message || data.error ||
            `Request failed: ${response.status}`
        );
    }

    return data;
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function createTextElement(tagName, className, text) {
    const element = document.createElement(tagName);

    if (className) element.className = className;
    element.textContent = text ?? "";

    return element;
}

function showEmptyState(container, message, className) {
    if (!container) return;

    container.replaceChildren(
        createTextElement("div", className || "", message)
    );
}

function formatDate(value) {
    if (!value) return "Date unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Date unavailable";
    }

    return date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function getEmergencyType(emergency) {
    if (!emergency) return "Emergency Request";

    return (
        emergency.emergency_type ||
        emergency.patient_data?.emergency_type ||
        emergency.triage?.emergency_type ||
        "Emergency Request"
    );
}

function getPriority(record) {
    if (!record) return "Pending";

    return (
        record.triage?.prediction ||
        record.priority ||
        record.prediction ||
        "Pending"
    );
}

function isAvailable(status) {
    return String(status || "").trim().toLowerCase() === "available";
}

function isActive(status) {
    return String(status || "").trim().toLowerCase() === "active";
}

function isEnRoute(status) {
    return String(status || "").trim().toLowerCase() === "en route";
}

function sortNewestFirst(records) {
    return records.slice().sort((a, b) => {
        return new Date(b.created_at || 0) -
               new Date(a.created_at || 0);
    });
}

function getEmergencyId(emergency) {
    return emergency?.emergency_id || emergency?._id || "";
}

function getEmergencyForDispatch(dispatch, emergencies) {
    const id = String(dispatch.emergency_id || "");

    return emergencies.find(emergency =>
        String(getEmergencyId(emergency)) === id
    );
}


/* ================= LOAD AMBULANCES ================= */

async function loadAmbulances() {
    const fleetList = document.querySelector(".fleet-list");

    try {
        const data = await fetchAdminData("/api/admin/ambulances");
        const ambulances = data.active_ambulances || [];

        const available = ambulances.filter(item =>
            isAvailable(item.status)
        ).length;

        setText("totalAmbulanceCount", ambulances.length);
        setText("availableAmbulanceCount", available);

        if (fleetList) {
            fleetList.replaceChildren();

            if (!ambulances.length) {
                showEmptyState(
                    fleetList,
                    "No ambulance records found",
                    "fleet-item"
                );
            }

            ambulances.forEach(ambulance => {
                const item = document.createElement("div");
                item.className = "fleet-item";

                const icon = createTextElement(
                    "div",
                    "fleet-icon",
                    "🚑"
                );

                const info = document.createElement("div");
                info.className = "fleet-info";

                info.append(
                    createTextElement(
                        "strong",
                        "",
                        ambulance.ambulance_id || "Unknown ID"
                    ),
                    createTextElement(
                        "span",
                        "",
                        ambulance.vehicle || "Emergency Vehicle"
                    )
                );

                const statusClass = isAvailable(ambulance.status)
                    ? "available"
                    : "busy";

                const status = createTextElement(
                    "span",
                    `fleet-status ${statusClass}`,
                    ambulance.status || "Unknown"
                );

                item.append(icon, info, status);
                fleetList.appendChild(item);
            });
        }

        return ambulances;

    } catch (error) {
        console.error("Ambulance API error:", error);

        if (fleetList) {
            showEmptyState(
                fleetList,
                "Unable to load ambulance data",
                "fleet-item"
            );
        }

        setText("availableAmbulanceCount", "—");
        setText("totalAmbulanceCount", "—");

        return null;
    }
}


/* ================= RESOLVE EMERGENCY ================= */

async function resolveEmergency(emergencyId, button) {
    if (!emergencyId) {
        alert("This emergency does not have a valid ID.");
        return;
    }

    const confirmed = confirm(
        "Resolve this emergency and complete its active ambulance dispatch?"
    );

    if (!confirmed) return;

    const originalText = button.textContent;

    button.disabled = true;
    button.textContent = "Resolving...";

    try {
        const response = await fetch(
            `${ADMIN_API_URL}/api/admin/resolve-emergency`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    emergency_id: emergencyId
                })
            }
        );

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(
                result.message ||
                result.error ||
                "Unable to resolve emergency."
            );
        }

        alert(
            "Emergency resolved successfully.\n" +
            "Dispatch: Completed\n" +
            "Ambulance: " +
            (result.ambulance_id || "Not specified")
        );

        await refreshDashboard();

    } catch (error) {
        console.error("Resolve emergency error:", error);

        alert(
            error.message ||
            "Resolution failed. Please refresh and try again."
        );

        button.disabled = false;
        button.textContent = originalText;
    }
}


/* ================= LOAD EMERGENCIES ================= */

async function loadEmergencies() {
    const emergencyList = document.querySelector(".emergency-list");

    try {
        const data = await fetchAdminData("/api/admin/emergencies");
        const emergencies = data.emergencies || [];

        const active = emergencies.filter(item =>
            isActive(item.status)
        );

        setText("totalEmergencyCount", emergencies.length);
        setText("activeEmergencyCount", active.length);

        if (emergencyList) {
            emergencyList.replaceChildren();

            if (!emergencies.length) {
                showEmptyState(
                    emergencyList,
                    "No emergency records found",
                    "emergency-item"
                );
            }

            sortNewestFirst(emergencies).slice(0, 10).forEach(emergency => {
                const item = document.createElement("div");
                item.className = "emergency-item";

                const info = document.createElement("div");

                info.append(
                    createTextElement(
                        "strong",
                        "",
                        getEmergencyType(emergency)
                    ),
                    createTextElement(
                        "span",
                        "",
                        `Priority: ${getPriority(emergency)}`
                    ),
                    createTextElement(
                        "span",
                        "",
                        `Status: ${emergency.status || "Unknown"}`
                    ),
                    createTextElement(
                        "span",
                        "",
                        `Ambulance: ${
                            emergency.ambulance_id || "Not assigned"
                        }`
                    ),
                    createTextElement(
                        "span",
                        "",
                        formatDate(emergency.created_at)
                    )
                );

                item.appendChild(info);

                // Show the Resolve button only for active emergencies.
                if (isActive(emergency.status)) {
                    const resolveButton = createTextElement(
                        "button",
                        "resolve-emergency-btn",
                        "Resolve Emergency"
                    );

                    resolveButton.type = "button";

                    const emergencyId = getEmergencyId(emergency);

                    if (!emergencyId) {
                        resolveButton.disabled = true;
                        resolveButton.title =
                            "Emergency ID is unavailable.";
                    } else {
                        resolveButton.addEventListener("click", () => {
                            resolveEmergency(
                                emergencyId,
                                resolveButton
                            );
                        });
                    }

                    item.appendChild(resolveButton);
                }

                emergencyList.appendChild(item);
            });
        }

        return emergencies;

    } catch (error) {
        console.error("Emergency API error:", error);

        if (emergencyList) {
            showEmptyState(
                emergencyList,
                "Unable to load emergency records",
                "emergency-item"
            );
        }

        setText("activeEmergencyCount", "—");
        setText("totalEmergencyCount", "—");

        return null;
    }
}


/* ================= LOAD DISPATCHES ================= */

async function loadDispatches() {
    try {
        const data = await fetchAdminData("/api/admin/dispatches");
        const dispatches = data.dispatches || [];

        setText("totalDispatchCount", dispatches.length);

        return dispatches;

    } catch (error) {
        console.error("Dispatch API error:", error);
        setText("totalDispatchCount", "—");
        return null;
    }
}


/* ================= RECENT ACTIVITY ================= */

function loadRecentActivity(emergencies, dispatches) {
    const container = document.getElementById("recentActivityList");

    if (!container) return;

    container.replaceChildren();

    const activities = [];

    emergencies.forEach(emergency => {
        activities.push({
            title: getEmergencyType(emergency),
            type: "Emergency",
            detail:
                `Priority: ${getPriority(emergency)} · ` +
                `Status: ${emergency.status || "Unknown"}`,
            date: emergency.created_at
        });
    });

    dispatches.forEach(dispatch => {
        activities.push({
            title: `Ambulance ${dispatch.ambulance_id || "Dispatch"}`,
            type: "Dispatch",
            detail:
                `Priority: ${dispatch.priority || "Unknown"} · ` +
                `Status: ${dispatch.status || "Unknown"}`,
            date: dispatch.created_at
        });
    });

    activities.sort((a, b) =>
        new Date(b.date || 0) - new Date(a.date || 0)
    );

    const recent = activities.slice(0, 5);

    if (!recent.length) {
        showEmptyState(
            container,
            "No recent activity available",
            "activity-item"
        );
        return;
    }

    recent.forEach(activity => {
        const item = document.createElement("div");
        item.className = "activity-item";

        item.append(
            createTextElement("strong", "", activity.title),
            createTextElement("span", "", activity.type),
            createTextElement("p", "", activity.detail),
            createTextElement(
                "small",
                "",
                formatDate(activity.date)
            )
        );

        container.appendChild(item);
    });
}


/* ================= DYNAMIC REALLOCATION ================= */

async function reallocateDispatch(dispatchId, button) {
    if (!dispatchId) {
        alert("This dispatch does not have a valid dispatch ID.");
        return;
    }

    const confirmed = confirm(
        "Reallocate this active dispatch to another available ambulance?"
    );

    if (!confirmed) return;

    const originalText = button.textContent;

    button.disabled = true;
    button.textContent = "Reallocating...";

    try {
        const response = await fetch(
            `${ADMIN_API_URL}/api/admin/reallocate`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    dispatch_id: dispatchId
                })
            }
        );

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(
                result.message ||
                result.error ||
                "Unable to reallocate ambulance."
            );
        }

        alert(
            "Reallocation successful!\n" +
            `Previous ambulance: ${
                result.previous_ambulance_id || "Unknown"
            }\n` +
            `New ambulance: ${
                result.ambulance?.ambulance_id || "Assigned"
            }`
        );

        await refreshDashboard();

    } catch (error) {
        console.error("Reallocation error:", error);

        alert(error.message || "Reallocation failed. Please try again.");

        button.disabled = false;
        button.textContent = originalText;
    }
}


/* ================= RENDER DISPATCH CONTROLS ================= */

function renderReallocationControls(dispatches, emergencies) {
    const emergencyList = document.querySelector(".emergency-list");

    if (!emergencyList) return;

    const activeDispatches = dispatches.filter(dispatch =>
        isEnRoute(dispatch.status)
    );

    if (!activeDispatches.length) return;

    const section = document.createElement("section");
    section.className = "admin-reallocation-section";

    const heading = createTextElement(
        "h3",
        "",
        "Active Dispatch Management"
    );

    const description = createTextElement(
        "p",
        "",
        "Reassign an active dispatch when another ambulance is available."
    );

    section.append(heading, description);

    activeDispatches.forEach(dispatch => {
        const row = document.createElement("div");
        row.className = "admin-reallocation-row";

        const emergency = getEmergencyForDispatch(
            dispatch,
            emergencies
        );

        const details = document.createElement("div");

        details.append(
            createTextElement(
                "strong",
                "",
                getEmergencyType(emergency || {
                    emergency_type: dispatch.emergency_type
                })
            ),
            createTextElement(
                "span",
                "",
                `Dispatch: ${dispatch.dispatch_id || "ID unavailable"}`
            ),
            createTextElement(
                "span",
                "",
                `Assigned: ${dispatch.ambulance_id || "Unknown"}`
            ),
            createTextElement(
                "span",
                "",
                `Priority: ${dispatch.priority || "Unknown"}`
            )
        );

        const button = createTextElement(
            "button",
            "reallocate-ambulance-btn",
            "Reallocate"
        );

        button.type = "button";

        if (!dispatch.dispatch_id) {
            button.disabled = true;
            button.title =
                "Reload dispatch data to obtain a dispatch ID.";
        } else {
            button.addEventListener("click", () => {
                reallocateDispatch(
                    dispatch.dispatch_id,
                    button
                );
            });
        }

        row.append(details, button);
        section.appendChild(row);
    });

    emergencyList.appendChild(section);
}


/* ================= REFRESH DASHBOARD ================= */

async function refreshDashboard() {
    const [ambulances, emergencies, dispatches] = await Promise.all([
        loadAmbulances(),
        loadEmergencies(),
        loadDispatches()
    ]);

    if (
        ambulances !== null &&
        emergencies !== null &&
        dispatches !== null
    ) {
        loadRecentActivity(emergencies, dispatches);
        renderReallocationControls(dispatches, emergencies);
    } else {
        const activity = document.getElementById("recentActivityList");

        if (activity) {
            showEmptyState(
                activity,
                "Unable to load all recent activity",
                "activity-item"
            );
        }
    }
}


/* ================= INITIALIZE ================= */

document.addEventListener("DOMContentLoaded", refreshDashboard);
