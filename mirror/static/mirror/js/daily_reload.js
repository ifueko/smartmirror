function scheduleModuleRefresh() {
  const now = new Date();
  const nextMidnight = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + 1,
    0, 0, 0
  );
  const msUntilMidnight = nextMidnight - now;
  //const msUntilMidnight = 5000; // 5 seconds for testing
  const msDaily = 24 * 60 * 60 * 1000;
  //const msDaily = 5000; // 5 seconds for testing

  setTimeout(() => {
    // Custom events your modules can listen for
    document.dispatchEvent(new Event("reload-affirmation"));
    document.dispatchEvent(new Event("reload-vision-board"));
    // Set recurring refresh every 24h
    setInterval(() => {
      document.dispatchEvent(new Event("reload-affirmation"));
      document.dispatchEvent(new Event("reload-vision-board"));
    }, msDaily);
  }, msUntilMidnight);
}

document.addEventListener("DOMContentLoaded", scheduleModuleRefresh);
