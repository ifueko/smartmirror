document.addEventListener("DOMContentLoaded", loadVisionBoard);
document.addEventListener("reload-vision-board", loadVisionBoard);

function openVisionModal(src) {
  const modal = document.getElementById("visionImageModal");
  const body = document.getElementById("visionImageModalBody");
  const modalImage = document.getElementById("visionImage");
  modalImage.src = src;
  const modalInstance = new bootstrap.Modal(modal);
  modalInstance.show();
}

async function loadVisionBoard() {
  const res = await fetch("/vision-board-feed");
  const data = await res.json();
  const images = data.images;
  const numCols = 4;

  const container = document.getElementById("vision-board");
  container.innerHTML = "";

  const columns = [];

  for (let i = 0; i < numCols; i++) {
    const col = document.createElement("div");
    col.className = "vision-col" + (i % 2 === 1 ? " reverse" : "");
    container.appendChild(col);
    columns.push(col);
  }

  const chunkSize = Math.ceil(images.length / numCols);
  for (let i = 0; i < numCols; i++) {
    const wrapper = document.createElement("div");
    wrapper.className = "vision-wrapper";
    const chunk = images.slice(i * chunkSize, (i + 1) * chunkSize);

    [...chunk, ...chunk].forEach((src) => {
      const container = document.createElement("div");
      container.className = "vision-img-container";

      const img = document.createElement("img");
      img.src = src;
      img.className = "vision-img";

      const button = document.createElement("button");
      button.className = "magnify-button";
      button.innerHTML = "🔍";
      button.onclick = () => openVisionModal(src);

      container.appendChild(img);
      container.appendChild(button);
      wrapper.appendChild(container);
    });

    columns[i].appendChild(wrapper);
  }
}
