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

function getStatusClass(status) {
  if (status === "Done") return "badge-done";
  if (status === "In progress") return "badge-in-progress";
  if (status === "Not started") return "badge-not-started";
  return "";
}

async function loadTasks() {
  const res = await fetch("/task-feed/");
  const data = await res.json();
  const list = document.getElementById("task-list");
  list.innerHTML = "";

  if (!data.tasks || data.tasks.length === 0) {
    list.innerHTML = "<li class='text-muted'>No tasks for today.</li>";
    return;
  }

  data.tasks.forEach((group) => {
    const parent = document.createElement("li");
    parent.className = "list-group-item fw-bold parent-task";
    parent.textContent = `📝 ${group.parent.title}`;
    parent.style.cursor = "pointer";

    const ul = document.createElement("ul");
    ul.className = "list-group mb-2 collapse-group";

    group.children.forEach((task) => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex justify-content-between align-items-center ps-4";

      // === Left Side: Checkbox + Label ===
      const leftWrapper = document.createElement("div");
      leftWrapper.className = "d-flex align-items-center";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = task.status === "Done";
      checkbox.className = "form-check-input me-2";

      checkbox.addEventListener("change", async () => {
        const newStatus = checkbox.checked ? "Done" : "In progress";
        await fetch("/tasks/update", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
          },
          body: JSON.stringify({
            page_id: task.id,
            status: newStatus,
          }),
        });
        document.dispatchEvent(new Event("reload-task-list"));
      });

      const label = document.createElement("span");
      label.textContent = task.title;
      if (task.status === "Done" && task.completed_today) {
        label.className = "text-muted text-decoration-line-through opacity-50";
      } else if (task.status === "Done") {
        label.className = "text-muted text-decoration-line-through";
      }

      leftWrapper.appendChild(checkbox);
      leftWrapper.appendChild(label);

      // === Right Side: Badge ===
      const badge = document.createElement("span");
      badge.className = `badge rounded-pill ms-2 ${getStatusClass(task.status)}`;
      badge.textContent = task.status;

      li.appendChild(leftWrapper);
      li.appendChild(badge);
      ul.appendChild(li);
    });

    parent.addEventListener("click", () => {
      ul.classList.toggle("d-none");
    });

    //list.appendChild(parent);
    //if (group.children.length) list.appendChild(ul);
    list.appendChild(parent);
    if (group.children.length) {
      ul.classList.add("d-none");  // collapse by default
      list.appendChild(ul);
    }
  });
}

document.addEventListener("DOMContentLoaded", loadTasks);
document.addEventListener("reload-task-list", loadTasks);
setInterval(() => {
  document.dispatchEvent(new Event("reload-task-list"));
}, 10 * 60 * 1000);
