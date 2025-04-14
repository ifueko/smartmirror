document.addEventListener("DOMContentLoaded", () => {
  const mirrorBtn = document.getElementById("btn-mirror");
  mirrorBtn.addEventListener("click", () => {
    document.body.classList.toggle("mirror-mode");
  });
});
