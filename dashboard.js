
(() => {
    "use strict";

    const API_BASE_URL = "http://127.0.0.1:5000";

    const token = localStorage.getItem("smartemsToken");

    function setText(selector, value) {
        const element = document.querySelector(selector);
        if (element) element.textContent = value;
    }

    function formatDate(value) {
        if (!value) return "Date unavailable";

        const date = new Date(value);

        return Number.isNaN(date.getTime())
            ? "Date unavailable"
            : date.toLocaleString();
    }

    function displayMessage(container, message) {
        if (!container) return;

        container.replaceChildren();

        const paragraph = document.createElement("p");
        paragraph.textContent = message;
        container.appendChild(paragraph);
    }

    function renderEmergencyHistory(emergencies) {
        const container = document.querySelector(".recent-activity");

        if (!container) return;

        const heading = container.querySelector("h2, h3");
        container.replaceChildren();

        if (heading) container.appendChild(heading);

        if (!emergencies.length) {
            const empty = document.createElement("p");
            empty.textContent = "No emergency requests yet.";
            container.appendChild(empty);
            return;
        }

        emergencies.slice(0, 5).forEach((emergency) => {
            const item = document.createElement("div");
            item.className = "dashboard-emergency-item";

            const title = document.createElement("h4");
            title.textContent =
                emergency.emergency_type || "Emergency Request";

            const details = document.createElement("p");
            details.textContent =
                `Status: ${emergency.status || "Unknown"} · ` +
                `Priority: ${emergency.triage?.prediction || "Not available"}`;

            const date = document.createElement("small");
            date.textContent = formatDate(emergency.created_at);

            item.append(title, details, date);
            container.appendChild(item);
        });
    }

    async function loadDashboard() {
        if (!token) {
            window.location.href = "login.html";
            return;
        }

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/user/dashboard`,
                {
                    method: "GET",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Accept": "application/json"
                    }
                }
            );

            const result = await response.json();

            if (response.status === 401 || response.status === 403) {
                localStorage.removeItem("smartemsToken");
                localStorage.removeItem("smartemsUser");
                localStorage.removeItem("smartemsRole");

                window.location.href = "login.html";
                return;
            }

            if (!response.ok || !result.success) {
                throw new Error(
                    result.message || "Unable to load dashboard."
                );
            }

            const profile = result.profile || {};
            const statistics = result.statistics || {};
            const emergencies = result.emergencies || [];

            // Save the latest profile returned by the backend.
            localStorage.setItem(
                "smartemsUser",
                JSON.stringify(profile)
            );

            // Update the existing profile placeholders.
            setText(".profile-card .profile-name", profile.name || "Not provided");
            setText(".profile-card .profile-email", profile.email || "Not provided");
            setText(".profile-card .profile-phone", profile.phone || "Not provided");

            // Update the welcome heading where possible.
            const welcome = document.querySelector(".welcome-section h1");

            if (welcome) {
                welcome.textContent = `Welcome back, ${profile.name || "there"}.`;
            }

            // Find the existing dashboard stat cards by their labels.
            document.querySelectorAll(".stat-card").forEach((card) => {
                const label = (
                    card.querySelector("h3, h4, p, .stat-label")
                        ?.textContent || ""
                ).toLowerCase();

                const value = card.querySelector(
                    ".stat-value, .stat-number, .stat-card h2, .stat-card h3"
                );

                if (!value) return;

                if (label.includes("active request")) {
                    value.textContent = statistics.active_emergencies ?? 0;
                } else if (label.includes("emergency case")) {
                    value.textContent = statistics.total_emergencies ?? 0;
                }
            });

            renderEmergencyHistory(emergencies);

            const activeEmergency = emergencies.find(
                (item) =>
                    String(item.status || "").toLowerCase() === "active"
            );

            const statusElement = document.querySelector(
                ".emergency-status, .current-status"
            );

            if (statusElement) {
                statusElement.textContent = activeEmergency
                    ? "Emergency Active"
                    : "Ready";
            }

        } catch (error) {
            console.error("SmartEMS dashboard error:", error);

            const container = document.querySelector(".recent-activity");

            displayMessage(
                container,
                "Unable to load dashboard data. Check that the backend is running."
            );
        }
    }

    document.addEventListener("DOMContentLoaded", loadDashboard);
})();
