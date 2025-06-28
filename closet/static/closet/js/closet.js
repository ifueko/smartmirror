document.addEventListener("DOMContentLoaded", loadCloset);
document.addEventListener("reload-closet", loadCloset);

var daily_outfit_data = {};
var weekly_outfit_data = [];

const STYLE_EMOJIS = {
  Casual: "🧢",
  Formal: "🎩",
  Vintage: "📻",
  Modern: "🖼️",
  Bohemian: "🌻",
  Sporty: "🏃",
  Professional: "💼",
  Minimalist: "📦"
  };

const SEASON_EMOJIS = {
  Spring: "🌸",
  Summer: "☀️",
  GFall: "🍂",
  Winter: "❄️",
  "All Seasons": "🌀"
};

async function drawDailyOutfitGrid() {
  console.log("Fetching today's outfit") 
  const res = await fetch("/daily-outfit");
  const outfit = await res.json();
  daily_outfit_data = outfit 
  daily_title = document.getElementById("dailyOutfitsModalTitle");
  daily_title.innerHTML = `Outfit for ${outfit.date}`;
  drawOutfitGridFullscreen(outfit.items, "outfitGrid");
}

function drawOutfitGridFullscreen(outfit_items, id) {
  const grid = document.getElementById(id);
  const iconDiv = document.getElementById(`${id}Overflow`);
  grid.innerHTML = "";
  iconDiv.innerHTML = "";
  var rowDiv = document.createElement("div");
  rowDiv.className = 'row h-100 w-100';
  grid.appendChild(rowDiv); 
  if (outfit_items.length == 0) {
    const buttonDiv = document.createElement("div");
    buttonDiv.className = "button-div d-flex justify-content-center"
    const addButton = document.createElement("button");
    addButton.className = "btn add-button";
    addButton.innerHTML = "+";
    // TODO(ifueko): add functions for generation to plus depending on date and class id, add title to button
    addButton.onclick = function() { alert('generate outfit'); };
    buttonDiv.appendChild(addButton);
    rowDiv.appendChild(buttonDiv);
  }
  for (let i = 0; i < outfit_items.length; i++) {
    const imgDiv = document.createElement("div");
    const img = document.createElement("img");
    const url = outfit_items[i].url;
    img.src = url;
    imgDiv.appendChild(img);
    img.className = 'outfit-img h-100 w-100';
    if (i == 0) {
      if (outfit_items.length == 1) {
        imgDiv.className = 'col-12-100';
        img.style.borderRadius = '25px';
      } else {
        imgDiv.className = 'col-12 h-50';
        img.style.borderTopLeftRadius = '25px';
        img.style.borderTopRightRadius = '25px';
      }
    } else if (i == 1) {
      img.style.borderBottomLeftRadius = '25px';
      if (outfit_items.length == 2) {
        imgDiv.className = 'col-12 h-50';
        img.style.borderBottomRightRadius = '25px';
      } else {
        imgDiv.className = 'col-6 h-50';
      }
    } else if (i == 2) {
      if (outfit_items.length == 3) {
        imgDiv.className = 'col-6 h-50';
        img.style.borderBottomRightRadius = '25px';
      } else {
        const thirdDiv = document.createElement("div");
        thirdDiv.className = "col-6 h-50";
        rowDiv.appendChild(thirdDiv);
        rowDiv = document.createElement("div");
        thirdDiv.appendChild(rowDiv);
        rowDiv.className = "row h-100 w-100";
        imgDiv.className = 'col-12 h-50';
      }
    } else if (i == 3) {
        imgDiv.className = 'col-12 h-50';
        img.style.borderBottomRightRadius = '25px';
    } else {
      imgDiv.className = 'daily-outfit-icon';
    }
    if (i > 3) {
      const imgIconDiv = document.createElement('div');
      imgIconDiv.className = 'p-2 icon-div';
      imgIconDiv.appendChild(imgDiv)
      iconDiv.appendChild(imgIconDiv);
    } else {
      rowDiv.appendChild(imgDiv);
    }
  }
}


async function drawWeeklyOutfitGrid() {
  console.log("Fetching Weekly Outfits...");
  const res = await fetch("/weekly-outfits");
  var outfits = await res.json();
  outfits = outfits.outfits;
  console.log(outfits);
  weekly_outfit_data = outfits;
  weekly_title = document.getElementById("weeklyOutfitsModalTitle");
  weekly_title.innerHTML = `Outfits for ${outfits[0].date} to ${outfits[6].date}`;
  for (let i = 0; i < 7; i++) {
    const outfit = outfits[i];
    drawOutfitGrid(outfit.items, `outfitGrid${i+1}`)
  }
}

function drawOutfitGrid(outfit_items, id) {
  const grid = document.getElementById(id);
  const iconDiv = document.getElementById(`${id}Overflow`);
  grid.innerHTML = "";
  iconDiv.innerHTML = "";
  var rowDiv = document.createElement("div");
  rowDiv.className = 'row h-100 w-100';
  grid.appendChild(rowDiv); 
  if (outfit_items.length == 0) {
    const buttonDiv = document.createElement("div");
    buttonDiv.className = "button-div d-flex justify-content-center"
    const addButton = document.createElement("button");
    addButton.className = "btn add-button";
    addButton.innerHTML = "+";
    // TODO(ifueko): add functions for generation to plus depending on date and class id, add title to button
    addButton.onclick = function() { alert('generate outfit'); };
    buttonDiv.appendChild(addButton);
    rowDiv.appendChild(buttonDiv);
  }
  for (let i = 0; i < outfit_items.length; i++) {
    const imgDiv = document.createElement("div");
    const img = document.createElement("img");
    img.className = 'outfit-img h-100 w-100';
    const url = outfit_items[i].url;
    img.src = url;
    imgDiv.appendChild(img);
    if (i == 0) {
      if (outfit_items.length == 1) {
        imgDiv.className = 'col-12 h-100';
        img.style.borderRadius = '25px';
      } else {
        imgDiv.className = 'col-12 h-50';
        img.style.borderTopLeftRadius = '25px';
        img.style.borderTopRightRadius = '25px';
      }
    } else if (i == 1) {
      img.style.borderBottomLeftRadius = '25px';
      if (outfit_items.length == 2) {
        imgDiv.className = 'col-12 h-50';
        img.style.borderBottomRightRadius = '25px';
      } else {
        imgDiv.className = 'col-6 h-50';
      }
    } else if (i == 2) {
      imgDiv.className = 'col-6 h-150';
      img.style.borderBottomRightRadius = '25px';
    } else {
      imgDiv.className = 'outfit-icon';
    }
    if (i > 2) {
      const imgIconDiv = document.createElement('div');
      imgIconDiv.className = 'p-2 icon-div';
      imgIconDiv.appendChild(imgDiv)
      iconDiv.appendChild(imgIconDiv);
    } else {
      rowDiv.appendChild(imgDiv);
    }
  }
}

function openClosetModal(src) {
  const modal = document.getElementById("closetImageModal");
  const body = document.getElementById("closetImageModalBody");
  const modalImage = document.getElementById("closetImage");
  const modalTitle = document.getElementById("closetTitle");
  modalTitle.innerHTML = src.name;
  modalImage.src = src.url;
  updateModalListing(src);
  const modalInstance = new bootstrap.Modal(modal);
  modalInstance.show();
}


async function openOutfitModal(modal_id) {
  const dailyOutfitModal = document.getElementById('dailyOutfitsModal');
  const weeklyOutfitModal = document.getElementById('weeklyOutfitsModal');
  let modal;
  if (modal_id == "dailyOutfitsModal") {
    modal = dailyOutfitModal;
  } else {
    modal = weeklyOutfitModal;
  }
  if (!dailyOutfitModal.classList.contains('show') && !weeklyOutfitModal.classList.contains('show')) {
    if (modal_id == "dailyOutfitsModal") {
      drawDailyOutfitGrid()
    } else {
      outfit_images = [];
      drawWeeklyOutfitGrid();
    }
    const modalInstance = new bootstrap.Modal(modal);
    modalInstance.show();
  }
}

function updateModalListing(src) {
  const listing = src.listing;
  // Color swatches
  const colorContainer = document.getElementById("colorSection");
  colorContainer.innerHTML = "";
  (Array.isArray(listing.Color) ? listing.Color : [listing.Color]).forEach(color => {
    const swatch = document.createElement("div");
    swatch.className = "color-swatch";
    swatch.style.backgroundColor = color.toLowerCase();
    colorContainer.appendChild(swatch);
  });

  document.getElementById("lastWorn").textContent = listing["Last Worn"] || "Never";
  document.getElementById("condition").textContent = listing["Condition"];
  document.getElementById("category").textContent = listing["Category"];
  document.getElementById("fit").textContent = listing["Fit"];

  // Seasons
  const seasonContainer = document.getElementById("season");
  seasonContainer.innerHTML = "";
  (listing.Season || []).forEach(season => {
    const tag = document.createElement("span");
    tag.textContent = `${SEASON_EMOJIS[season] || ""} ${season}`;
    seasonContainer.appendChild(tag);
  });

  // Style Tags
  const styleContainer = document.getElementById("styleTags");
  styleContainer.innerHTML = "";
  (listing["Style Tags"] || []).forEach(tag => {
    const tagEl = document.createElement("span");
    tagEl.textContent = `${STYLE_EMOJIS[tag] || ""} ${tag}`;
    styleContainer.appendChild(tagEl);
  });
}


async function loadCloset() {
  console.log("Fetching closet...");
  fetch("/update-outfits"); // Send update request for outfits ad DOM load and reset
  const res = await fetch("/closet-feed");
  const data = await res.json();
  const images = data.inventory;
  const numCols = 4;
  const chunkSize = Math.floor(images.length / numCols);
  const container = document.getElementById("closet");
  container.innerHTML = "";

  const columns = [];

  for (let i = 0; i < numCols; i++) {
    const col = document.createElement("div");
    col.className = "closet-col" + (i % 2 === 1 ? " reverse" : "");
    container.appendChild(col);
    columns.push(col);
  }
  for (let i = 0; i < numCols; i++) {
    const wrapper = document.createElement("div");
    wrapper.className = "closet-wrapper";
    const chunk = images.slice(i * chunkSize, (i + 1) * chunkSize);
    console.log(chunk.length);
    chunk.forEach((src) => {
      console.log(src);
      const container = document.createElement("div");
      container.className = "closet-img-container";

      const img = document.createElement("img");
      img.src = src.url;
      img.className = "closet-img";

      const button = document.createElement("button");
      button.className = "magnify-button";
      button.innerHTML = "🔍";
      button.onclick = () => openClosetModal(src);

      container.appendChild(img);
      container.appendChild(button);
      wrapper.appendChild(container);
    });

    columns[i].appendChild(wrapper);
  }
}
