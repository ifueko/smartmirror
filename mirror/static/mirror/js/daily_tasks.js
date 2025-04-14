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

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = task.status === "Complete";
      checkbox.className = "form-check-input me-2";

      checkbox.addEventListener("change", async () => {
        const newStatus = checkbox.checked ? "Complete" : "In Progress"; // or restore previous
        await fetch("/tasks/update/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: task.id,
            status: newStatus
          })
        });
        document.dispatchEvent(new Event("reload-task-list"));
      });

      const label = document.createElement("span");
      label.textContent = task.title;
      label.className = task.status === "Complete" ? "text-decoration-line-through text-muted" : "";

      li.prepend(checkbox);
      li.appendChild(label);

      const badge = document.createElement("span");
      badge.className = `badge rounded-pill ${
        task.status === "Complete" ? "bg-success" : "bg-warning text-dark"
      }`;
      badge.textContent = task.status;

      li.appendChild(badge);
      ul.appendChild(li);
    });

    parent.addEventListener("click", () => {
      ul.classList.toggle("d-none");
    });

    list.appendChild(parent);
    if (group.children.length) list.appendChild(ul);
  });
}

document.addEventListener("DOMContentLoaded", loadTasks);
document.addEventListener("reload-task-list", loadTasks);
setInterval(() => {
  document.dispatchEvent(new Event("reload-task-list"));
}, 10 * 60 * 1000);
