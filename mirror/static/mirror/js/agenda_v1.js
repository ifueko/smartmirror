function formatTimeRange(startStr, endStr) {
  const start = new Date(startStr);
  const end = new Date(endStr);

  const options = { hour: 'numeric', minute: '2-digit' };
  const startTime = start.toLocaleTimeString([], options);
  const endTime = end.toLocaleTimeString([], options);

  return `${startTime} – ${endTime}`;
}

function formatDateHeader(dateStr) {
  const date = new Date(dateStr);
  const today = new Date();

  const isToday = date.toDateString() === today.toDateString();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";

  const options = { weekday: 'long', month: 'short', day: 'numeric' };
  return date.toLocaleDateString(undefined, options);
}

async function loadAgenda() {
  const res = await fetch("/calendar-feed/");
  const data = await res.json();
  const container = document.getElementById("agenda-list");
  container.innerHTML = "";

  if (!data.events || data.events.length === 0) {
    container.innerHTML = "<div class='text-muted'>No upcoming events.</div>";
    return;
  }

  let lastDate = null;

  data.events.forEach((event) => {
    const start = new Date(event.start);
    const end = new Date(event.end);
    const dateLabel = start.toDateString();

    if (lastDate !== dateLabel) {
      const header = document.createElement("div");
      header.className = "fw-bold mt-3";
      header.textContent = formatDateHeader(start);
      container.appendChild(header);
      lastDate = dateLabel;
    }

    const item = document.createElement("div");
    item.className = "agenda-event small border-bottom border-secondary pb-2 mb-2";

    const timeRange = formatTimeRange(event.start, event.end);
    item.innerHTML = `
      <div class="fw-semibold">${timeRange}</div>
      <div>${event.title}</div>
      ${event.location ? `<div class="text-muted small">${event.location}</div>` : ""}
    `;

    container.appendChild(item);
  });
}

document.addEventListener("DOMContentLoaded", loadAgenda);
setInterval(loadAgenda, 10 * 60 * 1000); // Refresh every 10 minutes
