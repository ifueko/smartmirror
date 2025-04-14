document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".collapsible-header").forEach(header => {
    const targetId = header.getAttribute("data-target");
    const target = document.querySelector(targetId);
    const caret = header.querySelector(".caret-icon");

    if (target && caret) {
      // Default collapsed
      target.style.display = "block";
      caret.classList.add("expanded");

      header.addEventListener("click", () => {
        const isCollapsed = target.style.display === "none";
        target.style.display = isCollapsed ? "block" : "none";
        caret.classList.toggle("expanded", isCollapsed);
      });
    }
  });
});
