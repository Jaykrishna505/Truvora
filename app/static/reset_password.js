const form = document.querySelector("#reset-form");
const message = document.querySelector("#reset-message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  if (values.password !== values.confirmPassword) {
    setMessage("Passwords do not match.", "error");
    return;
  }

  setMessage("Updating password...", "info");
  const response = await fetch("/api/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: window.resetToken, password: values.password }),
  });
  const payload = await response.json();
  if (!response.ok) {
    setMessage(payload.detail || "Password could not be updated.", "error");
    return;
  }
  setMessage(payload.message, "success");
  form.classList.add("hidden");
});

function setMessage(text, tone) {
  message.textContent = text;
  message.className = `auth-message ${tone}`;
}
