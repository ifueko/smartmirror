function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const time_html = time.slice(0, -6) + '<span class="fadable">' + time.slice(5) + '</span>';
    document.getElementById("clock").innerHTML = time_html;
}
setInterval(updateClock, 1000);
updateClock();
