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
