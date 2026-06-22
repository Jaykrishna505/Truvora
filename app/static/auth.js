const registerForm = document.querySelector("#register-form");
const loginForm = document.querySelector("#login-form");
const forgotForm = document.querySelector("#forgot-form");
const message = document.querySelector("#auth-message");

document.querySelectorAll("[data-auth-tab]").forEach((button) => {
  button.addEventListener("click", () => showAuthView(button.dataset.authTab));
});

document.querySelector("#forgot-button").addEventListener("click", () => showAuthView("forgot"));
document.querySelector("#back-to-login").addEventListener("click", () => showAuthView("login"));

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuth("/api/auth/register", registerForm, "Creating account...");
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuth("/api/auth/login", loginForm, "Logging in...");
});

forgotForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage("Preparing reset link...", "info");
  const result = await api("/api/auth/forgot-password", {
    method: "POST",
    body: Object.fromEntries(new FormData(forgotForm)),
  });
  if (result.error) {
    setMessage(result.error, "error");
    return;
  }
  if (result.resetUrl) {
    message.innerHTML = `${escapeHtml(result.message)} <a href="${result.resetUrl}">Reset password now</a>`;
    message.className = "auth-message success";
    return;
  }
  setMessage(result.message, "success");
});

async function submitAuth(url, form, pendingText) {
  setMessage(pendingText, "info");
  const result = await api(url, { method: "POST", body: Object.fromEntries(new FormData(form)) });
  if (result.error) {
    setMessage(result.error, "error");
    return;
  }
  location.href = "/app";
}

function showAuthView(view) {
  registerForm.classList.toggle("hidden", view !== "register");
  loginForm.classList.toggle("hidden", view !== "login");
  forgotForm.classList.toggle("hidden", view !== "forgot");
  document.querySelector(".tabs").classList.toggle("hidden", view === "forgot");
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.authTab === view);
  });
  message.className = "auth-message hidden";
  message.textContent = "";
}

function setMessage(text, tone) {
  message.textContent = text;
  message.className = `auth-message ${tone}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json();
  return response.ok ? payload : { error: payload.detail || payload.error || "Request failed." };
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
