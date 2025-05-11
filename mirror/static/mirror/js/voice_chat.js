const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');

chatForm.addEventListener('submit', async e => {
  e.preventDefault();
  const text = chatInput.value.trim();
  const userBubble = document.createElement('div');
  userBubble.textContent = text;
  chatWindow.appendChild(userBubble);
  chatInput.value = "";
  userBubble.className="chat-bubble user";
  chatWindow.scrollTop = chatWindow.scrollHeight;
  try {
    const resp = await fetch("chat", {
      method: 'POST',
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken()
      },
      body: JSON.stringify({ message: text })
    });
    const data = await resp.json()
    console.log(data)
    const reply = data.response || data.error || '';
    const botBubble = document.createElement('div');
    botBubble.textContent = reply;
    chatWindow.appendChild(botBubble);
    botBubble.className="chat-bubble bot";
  } catch (err) {
    console.error(err);
  }
 });
