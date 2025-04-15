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
function renderTaskNode(task, depth = 0) {
  const li = document.createElement("li");
  li.className = "list-group-item d-flex justify-content-between align-items-start ps-" + (2 + depth * 2);

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
  if (task.status === "Done") {
    label.className = "text-muted text-decoration-line-through opacity-75";
  }

  leftWrapper.appendChild(checkbox);
  leftWrapper.appendChild(label);

  // === Right Side: Badge ===
  const badge = document.createElement("span");
  badge.className = `badge rounded-pill ms-2 ${getStatusClass(task.status)}`;

  const dateObj = task.date ? new Date(task.date) : null;
  const dateString = dateObj
    ? `📅 ${dateObj.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}`
    : "";

  badge.innerHTML = `<strong>${dateString}</strong> | ${task.status}`;

  li.appendChild(leftWrapper);
  li.appendChild(badge);

  const group = document.createElement("ul");
  group.className = "list-group collapse-group mb-2";
  if (task.children && task.children.length > 0) {
    const header = document.createElement("li");
    header.className = "list-group-item fw-bold parent-task ps-" + (1 + depth * 2);
    header.style.cursor = "pointer";
    header.innerHTML = `<span class="caret-icon me-2">▶</span> 📝 ${task.title}`; 

    header.addEventListener("click", () => {
      group.classList.toggle("d-none");
      const caret = header.querySelector(".caret-icon");
      caret?.classList.toggle("expanded");
    });
    group.classList.add("d-none");
      
  
    task.children.forEach(child => {
      group.appendChild(renderTaskNode(child, depth + 1));
    });
  
    const wrapper = document.createElement("div");
    wrapper.appendChild(header);
    wrapper.appendChild(group);
    return wrapper;
  } else {
    return li;
  }
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

  data.tasks.forEach(task => {
    list.appendChild(renderTaskNode(task));
  });
}

document.addEventListener("DOMContentLoaded", loadTasks);
document.addEventListener("reload-task-list", loadTasks);
setInterval(() => {
  document.dispatchEvent(new Event("reload-task-list"));
}, 10 * 60 * 1000);
