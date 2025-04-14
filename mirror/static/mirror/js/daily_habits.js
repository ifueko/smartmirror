function getCSRFToken() {
  const name = "csrftoken";
  const cookies = document.cookie.split("; ");
  for (let cookie of cookies) {
    if (cookie.startsWith(name + "=")) {
      return decodeURIComponent(cookie.split("=")[1]);
    }
  }
  return null;
}

async function loadHabits(emoji, containerId) {
  try {
    const res = await fetch(`/habits/${encodeURIComponent(emoji)}/`);
    const data = await res.json();
    const list = document.getElementById(containerId);
    list.innerHTML = "";

    if (!data.habits || data.habits.length === 0) {
      list.innerHTML = "<li class='text-muted'>No habits found.</li>";
      return;
    }
    const now = new Date();
    const hour = now.getHours();
    const shouldExpand = (
      (emoji === "☀️" && hour < 12) ||              // Morning before 12 PM
      ((emoji === "🌸" || emoji === "✨") && hour >= 12 && hour < 17) || // Daily/Weekly between 12–5 PM
      (emoji === "🌙" && hour >= 17)                // Evening after 5 PM
    );
    if (!shouldExpand) {
      list.classList.add("d-none");
    }

    data.habits.forEach((habit) => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex align-items-center";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = habit.done;
      checkbox.className = "form-check-input me-2";
      console.log(getCSRFToken());
      checkbox.addEventListener("change", async () => {
        let result = await fetch("/habits/update", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
          },
          body: JSON.stringify({
            page_id: habit.id,
            property: habit.property,
            done: checkbox.checked
          })
        }).then(response => {

        });
      });
      li.appendChild(checkbox);
      li.appendChild(document.createTextNode(habit.title.slice(2).trim()));
      list.appendChild(li);
    });
  } catch (error) {
    console.error(`Error loading habits for ${emoji}:`, error);
  }
}

function loadAllHabitSections() {
  const sections = {
    "☀️": "morning-list",
    "🌙": "evening-list",
    "🌸": "daily-list",
    "✨": "weekly-list"
  };

  for (const [emoji, containerId] of Object.entries(sections)) {
    loadHabits(emoji, containerId);
  }
}
document.addEventListener("DOMContentLoaded", loadAllHabitSections);
setInterval(loadAllHabitSections, 10 * 60 * 1000);
document.addEventListener("reload-habits", loadAllHabitSections);
