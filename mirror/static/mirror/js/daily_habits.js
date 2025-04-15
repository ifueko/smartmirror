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
    const list = document.getElementById(containerId);
    const section = list.closest(".habit-section");

    // Set default loading state
    list.innerHTML = "<li class='text-muted'><i>Loading...</i></li>";

    const res = await fetch(`/habits/${encodeURIComponent(emoji)}/`);
    const data = await res.json();
    const now = new Date();
    const hour = now.getHours();
    const shouldExpand = (
      (emoji === "☀️" && hour < 12) ||
      ((emoji === "🌸" || emoji === "✨") && hour >= 12 && hour < 17) ||
      (emoji === "🌙" && hour >= 17)
    );

    list.innerHTML = "";

    if (!data.habits || data.habits.length === 0) {
      list.innerHTML = "<li class='text-muted'>No habits found.</li>";
      return;
    }
    const caret = section.querySelector(".caret-icon");
    caret.addEventListener("click", () => {
      caret.classList.toggle("expanded");
      list.classList.toggle("d-none");
    });
    if (shouldExpand) {
      caret.classList.add("expanded");
    } else {
      list.classList.add("d-none");
    }

    data.habits.forEach((habit) => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex align-items-center";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = habit.done;
      checkbox.className = "form-check-input me-2";

      checkbox.addEventListener("change", async () => {
        await fetch("/habits/update", {
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
