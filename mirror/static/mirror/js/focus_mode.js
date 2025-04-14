document.addEventListener("DOMContentLoaded", () => {
  const focusButtons = document.querySelectorAll(".btn-focus");

  focusButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-focus-target");
      const size = btn.getAttribute("data-focus-size") || "";
      const originalSection = document.getElementById(targetId);

      if (originalSection) {
        const modal = document.getElementById("focusModal");
        const modalBody = document.getElementById("focusModalBody");
        const modalLabel = document.getElementById("focusModalLabel");
        const modalDialog = document.getElementById("focusModalDialog");

        // Reset modal dialog classes
        modalDialog.className = "modal-dialog"; // Clear previous size
        if (size === "fullscreen") {
          modalDialog.classList.add("modal-fullscreen");
        } else if (size === "lg") {
          modalDialog.classList.add("modal-lg");
        } else if (size === "md") {
          modalDialog.classList.add("modal-md");
        }

        // Set modal title from nearest .focus-title
        const focusTitle = btn.closest(".focus-container")?.querySelector(".focus-title")?.innerText;
        modalLabel.innerText = focusTitle || "Focus Mode";

        // Clear and clone section into modal
        modalBody.innerHTML = "";
        const clone = originalSection.cloneNode(true);
        clone.dataset.originalId = targetId;
        clone.classList.add("focus-clone");
        // Styling for scroll
        if (size === "fullscreen") {
          clone.style.height = "100%";           // Full height
          clone.style.maxHeight = "none";         // Don’t cap
          clone.style.overflowY = "scroll";       // Scroll if needed
        } else {
          clone.style.maxHeight = "80vh";         // Default modal sizing
          clone.style.overflowY = "auto";
        }

        modalBody.appendChild(clone);

        // Sync checkbox clicks to original
        clone.querySelectorAll("input[type='checkbox']").forEach((modalCheckbox, index) => {
          modalCheckbox.addEventListener("change", () => {
            const originalCheckbox = originalSection.querySelectorAll("input[type='checkbox']")[index];
            if (originalCheckbox) originalCheckbox.click();
          });
        });

        // Show modal
        const focusModal = new bootstrap.Modal(modal);
        focusModal.show();
      }
    });
  });
});
