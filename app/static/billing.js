const packageKey = new URLSearchParams(location.search).get("package") || "outreach";
const labels = {
  outreach: "Guest Outreach - $149 / month",
  reputation: "Reputation Management - $249 / month",
  social: "Social Management - $349 / month",
};

document.querySelector("#checkout-title").textContent = labels[packageKey] || labels.outreach;
document.querySelector("#pay-button").textContent = `Pay and activate ${labels[packageKey] || labels.outreach}`;

document.querySelector("#pay-button").addEventListener("click", async () => {
  const output = document.querySelector("#billing-message");
  output.classList.remove("hidden");
  output.value = "Processing local payment...";
  const response = await fetch("/api/payments/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ packageKey }),
  });
  const payload = await response.json();
  if (!response.ok) {
    output.value = payload.detail || "Payment failed.";
    return;
  }
  output.value = "Payment successful. Pro is active.";
  setTimeout(() => {
    location.href = "/app";
  }, 800);
});
