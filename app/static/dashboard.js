let me = null;
let requests = [];
let deliveries = [];
let filter = "all";

const titles = {
  dashboard: "Realtime requests",
  send: "Guest entry",
  deliveries: "Deliveries",
  settings: "Hotel settings",
  billing: "Billing",
};

boot();

async function boot() {
  me = await api("/api/me");
  if (me.error) {
    location.href = "/";
    return;
  }
  renderAccount();
  await loadRequests();
  await loadDeliveries();
  setupRealtime();
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderRequests();
  });
});

document.querySelector("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = await api("/api/requests", { method: "POST", body: Object.fromEntries(new FormData(event.currentTarget)) });
  const output = document.querySelector("#request-message");
  if (result.error) {
    showOutput(output, result.error);
    return;
  }
  showOutput(output, `Request created. Guest link: ${result.feedbackUrl}`);
  event.currentTarget.reset();
  await loadRequests();
  await loadDeliveries();
  switchView("dashboard");
});

document.querySelector("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = await api("/api/settings", { method: "PUT", body: Object.fromEntries(new FormData(event.currentTarget)) });
  showOutput(document.querySelector("#settings-message"), result.error || "Settings saved.");
  if (!result.error) {
    me = result;
    renderAccount();
  }
});

document.querySelector("#requests-table").addEventListener("change", async (event) => {
  if (!event.target.matches("[data-note-id]")) return;
  await api(`/api/requests/${event.target.dataset.noteId}/notes`, { method: "PUT", body: { notes: event.target.value } });
});

document.querySelector("#requests-table").addEventListener("click", async (event) => {
  if (!event.target.matches("[data-copy]")) return;
  await navigator.clipboard.writeText(event.target.dataset.copy);
  event.target.textContent = "Copied";
  setTimeout(() => {
    event.target.textContent = "Copy";
  }, 1200);
});

document.querySelector("#refresh-deliveries").addEventListener("click", loadDeliveries);

document.querySelector("#cancel-package-button").addEventListener("click", async () => {
  const confirmed = confirm("Cancellation requires 60 days notice. Your package stays active until the cancellation effective date. Request cancellation now?");
  if (!confirmed) return;
  const result = await api("/api/payments/cancel", { method: "POST" });
  if (result.error) {
    alert(result.error);
    return;
  }
  me = result;
  renderAccount();
});

document.querySelector("#package-grid").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-package]");
  if (!button) return;
  const packageKey = button.dataset.package;
  const isPaid = ["active", "cancel_pending"].includes(me.hotel.paymentStatus);
  const endpoint = isPaid ? "/api/payments/package-change" : "/api/payments/checkout";
  const payload = { packageKey };
  if (isPaid) {
    if (me.hotel.paymentStatus === "cancel_pending") {
      const choice = prompt(
        `Your subscription is currently scheduled to expire on ${formatDate(me.hotel.cancellationEffectiveAt)}.\n\nType KEEP to keep that expiry date and schedule the package change.\nType ACTIVE to remove the cancellation and keep the subscription active.`
      );
      if (!choice) return;
      const normalized = choice.trim().toUpperCase();
      if (!["KEEP", "ACTIVE"].includes(normalized)) {
        alert("Package change was not scheduled. Please type KEEP or ACTIVE.");
        return;
      }
      payload.keepSubscriptionActive = normalized === "ACTIVE";
    } else {
      const confirmed = confirm("Package changes take effect on your next renewal date. Schedule this package change?");
      if (!confirmed) return;
    }
  }
  const result = await api(endpoint, { method: "POST", body: payload });
  if (result.error) {
    alert(result.error);
    return;
  }
  if (isPaid) {
    me = result;
    renderAccount();
    return;
  }
  location.href = result.checkoutUrl;
});

async function loadRequests() {
  requests = await api("/api/requests");
  if (!Array.isArray(requests)) requests = [];
  renderRequests();
}

async function loadDeliveries() {
  deliveries = await api("/api/deliveries");
  if (!Array.isArray(deliveries)) deliveries = [];
  renderDeliveries();
}

function setupRealtime() {
  const source = new EventSource("/api/realtime");
  source.addEventListener("hello", () => {
    document.querySelector("#live-status").textContent = "Live connection active";
  });
  source.addEventListener("requests", (event) => {
    requests = JSON.parse(event.data);
    renderRequests();
  });
  source.addEventListener("deliveries", (event) => {
    deliveries = JSON.parse(event.data);
    renderDeliveries();
  });
  source.addEventListener("settings", (event) => {
    me = JSON.parse(event.data);
    renderAccount();
  });
  source.addEventListener("billing", (event) => {
    me = JSON.parse(event.data);
    renderAccount();
  });
  source.onerror = () => {
    document.querySelector("#live-status").textContent = "Live connection reconnecting...";
  };
}

function switchView(viewName) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#${viewName}-view`).classList.add("active");
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === viewName));
  document.querySelector("#page-title").textContent = titles[viewName];
}

function renderAccount() {
  document.querySelector("#hotel-name").textContent = me.hotel.name;
  document.querySelector("#account-email").textContent = me.user.email;
  const activePackage = (me.packages || []).find((item) => item.key === me.hotel.packageKey);
  document.querySelector("#plan-name").textContent = activePackage ? activePackage.name : "7-day trial";
  document.querySelector("#payment-status").textContent = `Payment status: ${me.hotel.paymentStatus}`;
  renderPackageExpiry();
  renderCancellationStatus();
  renderAccessBanner();
  renderPackages();
  const form = document.querySelector("#settings-form");
  form.elements.name.value = me.hotel.name;
  form.elements.googleLink.value = me.hotel.googleLink;
  form.elements.smsTemplate.value = me.hotel.smsTemplate;
  form.elements.emailTemplate.value = me.hotel.emailTemplate;
}

function renderAccessBanner() {
  const banner = document.querySelector("#access-banner");
  if (me.hotel.accessActive && me.hotel.accessReason === "trial") {
    banner.className = "access-banner trial";
    banner.innerHTML = `<strong>${me.hotel.trialDaysRemaining} trial day${me.hotel.trialDaysRemaining === 1 ? "" : "s"} remaining.</strong><span>Choose a package before the trial ends to keep the platform active.</span>`;
    return;
  }
  if (me.hotel.accessActive) {
    banner.className = "access-banner active";
    if (me.hotel.accessReason === "cancel_pending") {
      banner.innerHTML = `<strong>Cancellation notice active.</strong><span>Service package: ${document.querySelector("#plan-name").textContent}. Expires on ${formatDate(me.hotel.cancellationEffectiveAt)}.</span>`;
      return;
    }
    banner.innerHTML = `<strong>Platform active.</strong><span>Your ${document.querySelector("#plan-name").textContent} package is active.</span>`;
    return;
  }
  banner.className = "access-banner expired";
  if (me.hotel.accessReason === "cancelled") {
    banner.innerHTML = `<strong>Your package has ended.</strong><span>Choose a package in Billing to reactivate guest messaging and feedback links.</span>`;
    return;
  }
  banner.innerHTML = `<strong>Your 7-day trial has ended.</strong><span>Choose a package in Billing to reactivate guest messaging and feedback links.</span>`;
}

function renderPackageExpiry() {
  const expiry = document.querySelector("#package-expiry");
  if (me.hotel.paymentStatus === "cancel_pending" && me.hotel.cancellationEffectiveAt) {
    expiry.textContent = `Package expires: ${formatDate(me.hotel.cancellationEffectiveAt)}`;
    return;
  }
  if (me.hotel.subscriptionRenewsAt && ["active", "cancel_pending"].includes(me.hotel.paymentStatus)) {
    expiry.textContent = `Next renewal: ${formatDate(me.hotel.subscriptionRenewsAt)}`;
    return;
  }
  if (me.hotel.accessReason === "trial" && me.hotel.trialEndsAt) {
    expiry.textContent = `Trial expires: ${formatDate(me.hotel.trialEndsAt)}`;
    return;
  }
  expiry.textContent = "";
}

function renderCancellationStatus() {
  const status = document.querySelector("#cancellation-status");
  const button = document.querySelector("#cancel-package-button");
  button.classList.add("hidden");

  if (me.hotel.pendingPackageKey) {
    const pendingPackage = (me.packages || []).find((item) => item.key === me.hotel.pendingPackageKey);
    const pendingText = `${pendingPackage ? pendingPackage.name : "Package change"} starts on ${formatDate(me.hotel.pendingPackageEffectiveAt)}. Current package remains active until then.`;
    if (me.hotel.paymentStatus === "cancel_pending") {
      status.textContent = `${pendingText} Cancellation is still scheduled for ${formatDate(me.hotel.cancellationEffectiveAt)}.`;
      return;
    }
    status.textContent = `${pendingText} Subscription remains active.`;
    return;
  }

  if (me.hotel.paymentStatus === "cancel_pending") {
    status.textContent = `Cancellation requested. Your package remains active until ${formatDate(me.hotel.cancellationEffectiveAt)}.`;
    return;
  }

  if (me.hotel.paymentStatus === "active") {
    status.textContent = "Cancellation requires 60 days notice. Service remains active through the notice period.";
    button.classList.remove("hidden");
    return;
  }

  status.textContent = "";
}

function renderPackages() {
  const grid = document.querySelector("#package-grid");
  grid.innerHTML = (me.packages || [])
    .map((pkg) => {
      const active = me.hotel.packageKey === pkg.key && ["active", "cancel_pending"].includes(me.hotel.paymentStatus);
      const pending = me.hotel.pendingPackageKey === pkg.key;
      const paid = ["active", "cancel_pending"].includes(me.hotel.paymentStatus);
      const buttonLabel = active ? "Current package" : pending ? `Starts ${formatDate(me.hotel.pendingPackageEffectiveAt)}` : paid ? "Change next renewal" : `Choose $${pkg.price}`;
      return `
        <article class="plan-card package-card ${active ? "selected" : ""} ${pending ? "pending" : ""}">
          <p class="eyebrow">${active ? "Active package" : pending ? "Pending change" : "Package"}</p>
          <h2>${escapeHtml(pkg.name)}</h2>
          <div class="package-price">$${pkg.price}<span>/ month</span></div>
          <p>${escapeHtml(pkg.description)}</p>
          <ul>${pkg.features.map((feature) => `<li>${escapeHtml(feature)}</li>`).join("")}</ul>
          <button class="${active || pending ? "secondary-button" : "primary-button"}" ${active || pending ? "disabled" : `data-package="${pkg.key}"`}>${buttonLabel}</button>
        </article>
      `;
    })
    .join("");
}

function renderRequests() {
  const opened = requests.filter((item) => item.status === "opened" || item.status === "responded").length;
  const positive = requests.filter((item) => item.rating >= 4).length;
  const negative = requests.filter((item) => item.rating && item.rating < 4).length;
  document.querySelector("#sent-count").textContent = requests.length;
  document.querySelector("#opened-count").textContent = opened;
  document.querySelector("#positive-count").textContent = positive;
  document.querySelector("#negative-count").textContent = negative;

  const visible = requests.filter((item) => {
    if (filter === "positive") return item.rating >= 4;
    if (filter === "negative") return item.rating && item.rating < 4;
    return true;
  });

  const table = document.querySelector("#requests-table");
  if (!visible.length) {
    table.innerHTML = `<tr><td colspan="6" class="empty">No requests yet.</td></tr>`;
    return;
  }
  table.innerHTML = visible
    .map(
      (item) => `
        <tr>
          <td><strong>${escapeHtml(item.guestName)}</strong><span>${escapeHtml(item.email)}</span><span>${escapeHtml(item.phone)}</span><span>${formatDate(item.stayDate)}</span></td>
          <td><span class="status ${item.status}">${item.status}</span></td>
          <td>${ratingCell(item.rating)}</td>
          <td>${item.comments ? escapeHtml(item.comments) : "Awaiting feedback"}${completionCell(item)}</td>
          <td><a href="${item.feedbackUrl}" target="_blank">Open</a><button class="tiny-button" data-copy="${item.feedbackUrl}">Copy</button></td>
          <td><a href="${item.feedbackUrl}" target="_blank">Open</a><button class="tiny-button" data-copy="${item.feedbackUrl}">Copy</button>${googleClickCell(item)}</td>
          <td><textarea data-note-id="${item.id}" rows="2">${escapeHtml(item.notes)}</textarea></td>
        </tr>
      `
    )
    .join("");
}

function renderDeliveries() {
  const table = document.querySelector("#deliveries-table");
  if (!deliveries.length) {
    table.innerHTML = `<tr><td colspan="6" class="empty">No delivery records yet.</td></tr>`;
    return;
  }
  table.innerHTML = deliveries
    .map(
      (item) => `
        <tr>
          <td><strong>${escapeHtml(item.guestName)}</strong><span>${escapeHtml(item.guestEmail || item.guestPhone)}</span></td>
          <td>${escapeHtml(item.channel)}</td>
          <td>${escapeHtml(item.provider)}</td>
          <td><span class="status ${deliveryTone(item)}">${escapeHtml(item.status)}</span></td>
          <td class="message-cell">${escapeHtml(item.message)}</td>
          <td>${formatDateTime(item.createdAt)}</td>
        </tr>
      `
    )
    .join("");
}

function ratingCell(rating) {
  if (!rating) return "No response";
  return `<span class="rating ${rating >= 4 ? "good" : "watch"}">${rating} / 5</span>`;
}

function googleClickCell(item) {
  if (!item.googleClickedAt) return `<span class="google-clicked muted">Google not clicked</span>`;
  const count = Number(item.googleClickCount || 0);
  return `<span class="google-clicked">Google clicked ${formatDateTime(item.googleClickedAt)}${count > 1 ? ` (${count} times)` : ""}</span>`;
}

function completionCell(item) {
  if (!item.completedAt) return "";
  const label = item.completionType === "google" ? "Recorded before Google review" : "Private feedback recorded";
  return `<span class="completion-status">${label} ${formatDateTime(item.completedAt)}</span>`;
}

function deliveryTone(item) {
  if (item.status === "sent") return "responded";
  if (item.status === "failed") return "failed";
  return "opened";
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

function formatDate(value) {
  if (!value) return "";
  const date = String(value).includes("T") ? new Date(value) : new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function showOutput(output, text) {
  output.value = text;
  output.classList.toggle("hidden", !text);
}
