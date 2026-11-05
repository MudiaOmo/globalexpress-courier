const form = document.querySelector("#admin-login-form");
const message = document.querySelector("#login-message");

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;

  try {
    const response = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.elements.email.value,
        password: form.elements.password.value,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      message.textContent = result.error || "Unable to sign in.";
      return;
    }
    window.location.assign("/admin/dashboard");
  } catch {
    message.textContent = "Could not reach the server. Please try again.";
  } finally {
    submitButton.disabled = false;
  }
});
