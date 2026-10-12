
(() => {
    "use strict";

    const API_BASE_URL = "http://127.0.0.1:5000";

    function showMessage(form, message, success = false) {
        let box = form.querySelector(".auth-feedback");

        if (!box) {
            box = document.createElement("p");
            box.className = "auth-feedback";
            box.setAttribute("role", "status");
            box.style.marginTop = "12px";
            box.style.fontSize = "14px";
            form.appendChild(box);
        }

        box.textContent = message;
        box.style.color = success ? "green" : "#c62828";
    }

    async function postJSON(path, payload) {
        const response = await fetch(`${API_BASE_URL}${path}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        let result;

        try {
            result = await response.json();
        } catch {
            throw new Error("The server returned an invalid response.");
        }

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Request failed.");
        }

        return result;
    }

    function saveLogin(result) {
        localStorage.setItem("smartemsToken", result.token);
        localStorage.setItem(
            "smartemsUser",
            JSON.stringify(result.user)
        );
        localStorage.setItem("smartemsRole", result.role);
    }

    function setLoading(button, loading, originalText) {
        button.disabled = loading;
        button.textContent = loading ? "Please wait..." : originalText;
    }

    // USER LOGIN
    const loginForm = document.getElementById("loginForm");

    if (loginForm) {
        loginForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;
            const button = loginForm.querySelector(
                'button[type="submit"]'
            );

            setLoading(button, true, "Sign In");

            try {
                const result = await postJSON("/api/auth/login", {
                    email,
                    password
                });

                saveLogin(result);
                showMessage(loginForm, "Login successful. Redirecting...", true);

                window.location.href = "dashboard.html";
            } catch (error) {
                showMessage(loginForm, error.message);
            } finally {
                setLoading(button, false, "Sign In");
            }
        });
    }

    // USER SIGNUP
    const signupForm = document.getElementById("signupForm");

    if (signupForm) {
        signupForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const name = document.getElementById("name").value.trim();
            const email = document.getElementById("email").value.trim();
            const phone = document.getElementById("phone").value.trim();
            const password = document.getElementById("password").value;
            const confirmPassword =
                document.getElementById("confirmPassword").value;

            const button = signupForm.querySelector(
                'button[type="submit"]'
            );

            if (password !== confirmPassword) {
                showMessage(signupForm, "Passwords do not match.");
                return;
            }

            if (password.length < 8) {
                showMessage(
                    signupForm,
                    "Password must contain at least 8 characters."
                );
                return;
            }

            setLoading(button, true, "Create Account");

            try {
                await postJSON("/api/auth/signup", {
                    name,
                    email,
                    phone,
                    password
                });

                showMessage(
                    signupForm,
                    "Account created! Redirecting to login...",
                    true
                );

                window.location.href = "login.html";
            } catch (error) {
                showMessage(signupForm, error.message);
            } finally {
                setLoading(button, false, "Create Account");
            }
        });
    }

    // ADMIN LOGIN
    const adminLoginForm = document.getElementById("adminLoginForm");

    if (adminLoginForm) {
        adminLoginForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const email =
                document.getElementById("adminEmail").value.trim();
            const password =
                document.getElementById("adminPassword").value;

            const button = adminLoginForm.querySelector(
                'button[type="submit"]'
            );

            setLoading(button, true, "Sign In");

            try {
                const result = await postJSON("/api/auth/admin-login", {
                    email,
                    password
                });

                saveLogin(result);
                showMessage(
                    adminLoginForm,
                    "Administrator login successful. Redirecting...",
                    true
                );

                window.location.href = "admin-dashboard.html";
            } catch (error) {
                showMessage(adminLoginForm, error.message);
            } finally {
                setLoading(button, false, "Sign In");
            }
        });
    }
})();
