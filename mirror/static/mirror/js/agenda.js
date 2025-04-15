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

  if (isToday) return "Today";
  if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";

  const options = { weekday: 'long', month: 'short', day: 'numeric' };
  return date.toLocaleDateString(undefined, options);
}

function getEventDotClass(summary = "") {
  const lower = summary.toLowerCase();
  if (lower.includes("meeting")) return "dot-meeting";
  if (lower.includes("party") || lower.includes("friend")) return "dot-social";
  if (lower.includes("personal") || lower.includes("self")) return "dot-personal";
  return "dot-default";
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
  let todayStr = new Date().toDateString();

  data.events.forEach((event) => {
    const start = new Date(event.start);
    const end = new Date(event.end);
    const dateLabel = start.toDateString();

    let section = document.getElementById(`agenda-${dateLabel}`);

    if (!section) {
      // Create new section
      const header = document.createElement("div");
      header.className = "fw-bold mt-2";
      header.dataset.target = `agenda-${dateLabel}`;
      header.innerHTML = `<span class="caret-icon me-2">▶</span> ${formatDateHeader(start)}`;

      const content = document.createElement("ul");
      content.id = `agenda-${dateLabel}`;
      content.className = "list-group small collapsible-content";
      if (dateLabel === todayStr) {
        caret.classList.add("expanded");
      } else {
        content.classList.toggle("d-none");
      }

      container.appendChild(header);
      container.appendChild(content);

      section = content;
      header.addEventListener("click", () => {
        content.classList.toggle("d-none");
        const caret = header.querySelector(".caret-icon");
        caret?.classList.toggle("expanded");
      });

    }

    const li = document.createElement("li");
    li.className = "list-group-item bg-transparent border-0 p-1";

    const timeRange = formatTimeRange(event.start, event.end);
    const dotClass = getEventDotClass(event.title);

    li.innerHTML = `
      <span class="dot ${dotClass}"></span>
      🕒 ${timeRange} — <strong>${event.title}</strong>
      ${event.location ? ` • <span class="text-muted">${event.location}</span>` : ""}
    `;

    section.appendChild(li);
  });

  // Add header toggle listeners
  document.querySelectorAll(".collapsible-header").forEach(header => {
    const targetId = header.dataset.target;
    const target = document.getElementById(targetId);
    const caret = header.querySelector(".caret-icon");

    if (!target || !caret) return;

    if (target.classList.contains("expanded")) {
      caret.classList.add("expanded");
    }

    header.addEventListener("click", () => {
      target.classList.toggle("expanded");
      caret.classList.toggle("expanded");
    });
  });
}

document.addEventListener("DOMContentLoaded", loadAgenda);
setInterval(loadAgenda, 10 * 60 * 1000); // Reload every 10 minutes
