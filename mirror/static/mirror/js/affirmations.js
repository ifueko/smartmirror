async function loadAffirmations() {
    const box = document.getElementById("affirmations");
    try {
        const res = await fetch ("/affirmations-feed");
        const data = await res.json();
        var affirmation = "";
        const affirmations = data.affirmations;
        for (let i = 0; i < affirmations.length; i++) {
            affirmation += '"' + affirmations[i] + '"';
            if (i < affirmations.length - 1) {
                affirmation += "<br>";
            }
        }
        box.innerHTML = affirmation;
    } catch {
        box.textContent = "💖 You are aligned and becoming 💖";
    }
}
document.addEventListener("DOMContentLoaded", async () => {
    loadAffirmations();
});

document.addEventListener("reload-affirmation", async () => {
    loadAffirmations();
});        
