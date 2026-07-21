async function updateApiStatus() {
  const status = document.querySelector("#api-status");

  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error(`Health check returned ${response.status}`);
    }

    const data = await response.json();
    status.textContent = data.status === "ok" ? "API ready" : "API unavailable";
    status.classList.toggle("ready", data.status === "ok");
    status.classList.toggle("error", data.status !== "ok");
  } catch (_error) {
    status.textContent = "API unavailable";
    status.classList.add("error");
  }
}

updateApiStatus();

