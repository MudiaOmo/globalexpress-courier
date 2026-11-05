const shipmentList = document.querySelector("#shipment-list");
const dashboardMessage = document.querySelector("#dashboard-message");
const shipmentCount = document.querySelector("#shipment-count");
const activeCount = document.querySelector("#active-count");
const deliveredCount = document.querySelector("#delivered-count");
const latestStatus = document.querySelector("#latest-status");
const searchInput = document.querySelector("#shipment-search");
const statusFilter = document.querySelector("#shipment-status-filter");
const resultsCount = document.querySelector("#shipment-results-count");
let shipments = [];

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function addDetail(parent, label, value) {
  const item = document.createElement("div");
  item.append(makeElement("span", "", label), makeElement("strong", "", value || "—"));
  parent.append(item);
}

function renderHistory(history = []) {
  const details = document.createElement("details");
  details.className = "shipment-history";
  const summary = makeElement("summary", "", `Tracking history (${history.length})`);
  details.append(summary);
  if (history.length === 0) {
    details.append(makeElement("p", "empty-note", "No tracking updates have been posted."));
    return details;
  }

  const list = document.createElement("ol");
  list.className = "shipment-history-list";
  for (const event of [...history].reverse()) {
    const item = document.createElement("li");
    const heading = makeElement("strong", "", event.status || "Status update");
    const date = makeElement(
      "time",
      "",
      event.date ? new Date(event.date).toLocaleString() : "Date unavailable"
    );
    item.append(heading, date);
    if (event.location) item.append(makeElement("span", "", event.location));
    if (event.description) item.append(makeElement("p", "", event.description));
    list.append(item);
  }
  details.append(list);

  const latestLocation = [...history].reverse().find((event) => event.location)?.location;
  if (latestLocation) {
    const mapLink = document.createElement("a");
    mapLink.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(latestLocation)}`;
    mapLink.target = "_blank";
    mapLink.rel = "noopener noreferrer";
    mapLink.textContent = `View latest location: ${latestLocation}`;
    details.append(mapLink);
  }
  return details;
}

function renderShipment(shipment) {
  const card = makeElement("article", "shipment-card");
  const head = makeElement("div", "shipment-card-head");
  const tracking = document.createElement("div");
  tracking.append(
    makeElement("strong", "", shipment.tracking_number),
    makeElement("small", "", `Booked ${new Date(shipment.created_at).toLocaleString()}`)
  );
  head.append(tracking, makeElement("span", "status-pill", shipment.status));

  const details = makeElement("div", "shipment-details");
  addDetail(details, "FROM", `${shipment.sender_name} · ${shipment.sender_country}`);
  addDetail(details, "TO", `${shipment.receiver_name} · ${shipment.receiver_country}`);
  addDetail(details, "PARCEL", `${shipment.parcel_description} · ${shipment.weight} kg`);
  addDetail(details, "CUSTOMER EMAIL", shipment.customer_email);
  addDetail(details, "DELIVERY ADDRESS", shipment.delivery_address);
  if (shipment.customer_email) {
    const email = document.createElement("a");
    email.className = "shipment-email";
    email.href = `mailto:${encodeURIComponent(shipment.customer_email)}?subject=${encodeURIComponent(`Shipment ${shipment.tracking_number} update`)}`;
    email.textContent = "Email customer";
    details.append(email);
  }
  card.append(head, details, renderHistory(shipment.history));

  const form = makeElement("form", "status-form");
  form.dataset.trackingNumber = shipment.tracking_number;
  const statusLabel = makeElement("label", "", "New status");
  const statusInput = document.createElement("input");
  statusInput.name = "status";
  statusInput.required = true;
  statusInput.maxLength = 50;
  statusInput.placeholder = "In transit";
  statusLabel.append(statusInput);

  const locationLabel = makeElement("label", "", "Location");
  const locationInput = document.createElement("input");
  locationInput.name = "location";
  locationInput.maxLength = 150;
  locationInput.placeholder = "City or facility";
  locationLabel.append(locationInput);

  const descriptionLabel = makeElement("label", "", "Update note");
  const descriptionInput = document.createElement("input");
  descriptionInput.name = "description";
  descriptionInput.maxLength = 255;
  descriptionInput.placeholder = "Optional details";
  descriptionLabel.append(descriptionInput);

  const submit = makeElement("button", "button button-primary", "Post update →");
  submit.type = "submit";
  form.append(statusLabel, locationLabel, descriptionLabel, submit);
  card.append(form);
  return card;
}

function getVisibleShipments() {
  const query = searchInput.value.trim().toLocaleLowerCase();
  const selectedStatus = statusFilter.value;
  return shipments.filter((shipment) => {
    if (selectedStatus && shipment.status !== selectedStatus) return false;
    if (!query) return true;
    const searchable = [
      shipment.tracking_number,
      shipment.customer_email,
      shipment.sender_name,
      shipment.sender_country,
      shipment.receiver_name,
      shipment.receiver_country,
      shipment.parcel_description,
      shipment.delivery_address,
      shipment.status,
      ...(shipment.history || []).flatMap((event) => [
        event.status,
        event.location,
        event.description,
      ]),
    ].join(" ").toLocaleLowerCase();
    return searchable.includes(query);
  });
}

function renderShipments() {
  const visibleShipments = getVisibleShipments();
  resultsCount.textContent = `Showing ${visibleShipments.length} of ${shipments.length} shipments`;
  shipmentList.replaceChildren();
  if (visibleShipments.length === 0) {
    shipmentList.append(makeElement(
      "div",
      "empty-card",
      shipments.length ? "No shipments match your search or status filter." : "No shipments have been booked yet."
    ));
    return;
  }
  for (const shipment of visibleShipments) shipmentList.append(renderShipment(shipment));
}

function setStatusOptions() {
  const selected = statusFilter.value;
  const statuses = [...new Set(shipments.map((shipment) => shipment.status).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  statusFilter.replaceChildren(new Option("All statuses", ""));
  for (const status of statuses) statusFilter.add(new Option(status, status));
  statusFilter.value = statuses.includes(selected) ? selected : "";
}

async function loadShipments() {
  dashboardMessage.textContent = "";
  dashboardMessage.classList.remove("error");
  shipmentList.replaceChildren(makeElement("div", "loading-card", "Loading shipments…"));
  try {
    const response = await fetch("/api/admin/shipments");
    if (response.status === 401 || response.status === 403) {
      window.location.assign("/admin");
      return;
    }
    if (!response.ok) throw new Error("Unable to load shipments.");
    shipments = await response.json();
    shipmentCount.textContent = String(shipments.length);
    const delivered = shipments.filter((shipment) => /delivered/i.test(shipment.status)).length;
    const active = shipments.filter((shipment) =>
      !/(delivered|cancelled|canceled|returned)/i.test(shipment.status)
    ).length;
    deliveredCount.textContent = String(delivered);
    activeCount.textContent = String(active);
    latestStatus.textContent = shipments[0]?.status || "No shipments yet";
    setStatusOptions();
    renderShipments();
  } catch (error) {
    shipmentList.replaceChildren();
    dashboardMessage.textContent = error.message || "Unable to load shipments.";
    dashboardMessage.classList.add("error");
    resultsCount.textContent = "Shipment list unavailable";
  }
}

function csvCell(value) {
  let text = value == null ? "" : String(value);
  if (/^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function exportShipments() {
  const rows = getVisibleShipments();
  const headers = [
    "Tracking number", "Customer email", "Sender", "Origin", "Receiver",
    "Destination", "Delivery address", "Parcel", "Weight (kg)", "Status", "Booked at",
  ];
  const csv = [headers, ...rows.map((shipment) => [
    shipment.tracking_number,
    shipment.customer_email,
    shipment.sender_name,
    shipment.sender_country,
    shipment.receiver_name,
    shipment.receiver_country,
    shipment.delivery_address,
    shipment.parcel_description,
    shipment.weight,
    shipment.status,
    shipment.created_at,
  ])].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "shipments.csv";
  link.click();
  URL.revokeObjectURL(url);
}

shipmentList?.addEventListener("submit", async (event) => {
  const form = event.target.closest(".status-form");
  if (!form) return;
  event.preventDefault();
  dashboardMessage.textContent = "";
  dashboardMessage.classList.remove("error");
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;

  try {
    const response = await fetch(
      `/api/admin/shipments/${encodeURIComponent(form.dataset.trackingNumber)}/status`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: form.elements.status.value,
          location: form.elements.location.value,
          description: form.elements.description.value,
        }),
      }
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to post update.");
    const notification = result.email_notification;
    form.reset();
    await loadShipments();
    dashboardMessage.textContent = notification
      ? `${result.message} ${notification.message}`
      : result.message;
    if (notification && notification.status !== "sent") {
      dashboardMessage.classList.add("error");
    }
  } catch (error) {
    dashboardMessage.textContent = error.message || "Unable to post update.";
    dashboardMessage.classList.add("error");
  } finally {
    submit.disabled = false;
  }
});

searchInput?.addEventListener("input", renderShipments);
statusFilter?.addEventListener("change", renderShipments);
document.querySelector("#export-shipments")?.addEventListener("click", exportShipments);
document.querySelector("#refresh-shipments")?.addEventListener("click", loadShipments);
document.querySelector("#admin-logout")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const response = await fetch("/api/admin/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!response.ok) throw new Error("Unable to sign out.");
    window.location.assign("/admin");
  } catch (error) {
    dashboardMessage.textContent = error.message || "Unable to sign out.";
    dashboardMessage.classList.add("error");
  } finally {
    button.disabled = false;
  }
});
loadShipments();
