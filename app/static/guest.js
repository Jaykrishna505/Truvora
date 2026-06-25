let rating = null;

renderStars();

document.querySelectorAll("#stars button").forEach((button) => {
  button.addEventListener("click", () => {
    rating = Number(button.dataset.rating);
    renderStars();
    renderChoice();
  });
});

document.querySelector("#google-review-button").addEventListener("click", () => {
  trackGoogleClick();
});

document.querySelector("#feedback-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!rating) {
    showGuestMessage("Please select a star rating first.");
    return;
  }
  const comments = new FormData(event.currentTarget).get("comments");
  const response = await fetch(`/api/public/feedback/${window.feedbackToken}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating, comments }),
  });
  const payload = await response.json();
  if (response.ok) {
    showSubmittedState();
    return;
  }
  showGuestMessage(payload.detail || "Feedback could not be submitted.");
});

function renderStars() {
  document.querySelectorAll("#stars button").forEach((button) => {
    const isActive = rating && Number(button.dataset.rating) <= rating;
    button.classList.toggle("active", isActive);
    button.textContent = isActive ? "\u2605" : "\u2606";
  });
}

function renderChoice() {
  const choice = document.querySelector("#guest-choice");
  const message = document.querySelector("#guest-choice-message");
  const privateButton = document.querySelector("#private-feedback-button");
  const googleButton = document.querySelector("#google-review-button");
  choice.classList.remove("hidden");

  message.textContent = "Thanks for the rating.";
  privateButton.classList.add("hidden");
  googleButton.classList.add("hidden");
  privateButton.className = "primary-button hidden";
  googleButton.className = "primary-button hidden"

  if (rating >= 3) {
    googleButton.classList.remove("hidden");
    
    // googleButton.className = "primary-button";
    // privateButton.className = "secondary-button";
    // googleButton.style.order = "-1";
    // privateButton.style.order = "0";
    // return;
  }
  else{
    privateButton.classList.remove("hidden");
  }


  // privateButton.className = "primary-button";
  // googleButton.className = "secondary-button";
  // privateButton.style.order = "-1";
  // googleButton.style.order = "0";
}

function showGuestMessage(text) {
  const output = document.querySelector("#guest-message");
  output.value = text;
  output.classList.remove("hidden");
}

function showSubmittedState() {
  document.querySelector("#guest-form-fields").classList.add("hidden");
  document.querySelector("#guest-message").classList.add("hidden");
  document.querySelector("#submission-confirmation").classList.remove("hidden");
}

function trackGoogleClick() {
  const url = `/api/public/google-click/${window.feedbackToken}`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url);
    return;
  }
  fetch(url, { method: "POST", keepalive: true }).catch(() => {});
}
