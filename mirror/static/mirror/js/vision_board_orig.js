document.addEventListener("DOMContentLoaded", async () => {
  const res = await fetch("/vision-board-feed");
  const data = await res.json();
  const images = data.images;
  const numCols = 4;

  const container = document.getElementById("vision-board");
  const columns = [];

  for (let i = 0; i < numCols; i++) {
    const col = document.createElement("div");
    col.className = "vision-col" + (i % 2 === 1 ? " reverse" : "");
    container.appendChild(col);
    columns.push(col);
  }

  // Split images evenly among columns
  const chunkSize = Math.ceil(images.length / numCols);
  const chunks = [];
  for (let i = 0; i < numCols; i++) {
    const chunk = images.slice(i * chunkSize, (i + 1) * chunkSize);
    chunks.push(chunk);
  }

  // Fill columns with unique slice (duplicated for looping)
  columns.forEach((col, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "vision-wrapper";

    const columnImages = [...chunks[i], ...chunks[i]]; // duplicate for looping
    columnImages.forEach((src) => {
      const img = document.createElement("img");
      img.src = src;
      img.className = "vision-img";
      wrapper.appendChild(img);
    });

    col.appendChild(wrapper);
  });
});


async function loadVisionBoard() {
  const res = await fetch("/vision-board-feed");
  const data = await res.json();
  const images = data.images;
  const numCols = 4;

  const container = document.getElementById("vision-board");
  container.innerHTML = ""; // Clear existing content

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
      const img = document.createElement("img");
      img.src = src;
      img.className = "vision-img";
      wrapper.appendChild(img);
    });
    columns[i].appendChild(wrapper);
  }
}

document.addEventListener("DOMContentLoaded", loadVisionBoard);
document.addEventListener("reload-vision-board", loadVisionBoard);
