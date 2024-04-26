let cachedToken = null;
const host = "127.0.0.1:8000";

const getToken = async () => {
  try {
    if (cachedToken) {
      return cachedToken;
    }

    const response = await fetch("/token");
    if (!response.ok) {
      throw new Error("Failed to fetch token");
    }
    const data = await response.json();
    cachedToken = data.token;
    return data.token;
  } catch (error) {
    console.error("Error fetching token:", error);
    throw error;
  }
};

const headers = async () => {
  try {
    return {
      Authorization: `Bearer ${await getToken()}`,
    };
  } catch (error) {
    console.error("Error getting headers:", error);
    throw error;
  }
};

const groupList = async (host) => {
  try {
    const header = await headers();
    const response = await axios.get(`${host}/group/list`, {
      headers: header,
    });
    return response.data;
  } catch (error) {
    console.error(error.response ? error.response.data : error);
    throw error;
  }
};

const gclist = async () => {
  const groupUL = document.getElementById("group-list");
  const glist = await groupList(`http://${host}`);
  console.log(glist[0]);
  for (let i = 0; i < glist.length; i++) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.innerText = glist[i].name;
    a.href = `/chat/${glist[i].id}`;
    li.appendChild(a);
    groupUL.appendChild(li);
  }
};

const fetchMessages = async (id) => {
  try {
    const headers = {
      Authorization: `Bearer ${await getToken()}`,
    };
    const response = await axios.get(`http://${host}/${id}/message/fetch`);
    return response.data;
  } catch (error) {
    console.log(error);
  }
};

const connectWebSocket = async (id) => {
  try {
    const token = await getToken();
    const messages = await fetchMessages(id);
    console.log(messages);
    for (let i = messages.length - 1; i >= 0; i--) {
      displayMessage(messages[i]);
    }
    const websocket = new WebSocket(`ws://${host}/chat/${id}`);

    websocket.onopen = function (event) {
      console.log("WebSocket connection established.");
      websocket.send(token);
    };

    websocket.onmessage = function (event) {
      const message = JSON.parse(event.data);
      displayMessage(message);
    };

    websocket.onerror = function (error) {
      console.error("WebSocket error:", error);
    };

    websocket.onclose = function () {
      console.log("WebSocket connection closed.");
    };
    setInterval(() => {
      if (websocket.readyState !== WebSocket.OPEN) {
        console.log("WebSocket connection is not open. Reconnecting...");
      }
    }, 5000);

    return websocket;
  } catch (error) {
    console.error("Error connecting to WebSocket:", error);
    throw error;
  }
};

const wsMessageSend = async (id, content) => {
  try {
    const headers = {
      Authorization: `Bearer ${await getToken()}`,
    };
    const response = await axios.post(`http://${host}/${id}/message`, content, {
      headers,
    });
    console.log("Message sent:", response.data);
    return response.data;
  } catch (error) {
    console.error("Error sending message:", error);
    throw error;
  }
};

const sendMessage = async (id) => {
  const messageInput = document.getElementById("messageInput");
  const content = messageInput.value;
  const response = await wsMessageSend(id, { content });
  messageInput.value = ""
  return response;
};

function displayMessage(message) {
  const messagesDiv = document.getElementById("messages");
  const messageDiv = document.createElement("div");
  messageDiv.textContent = `${message.user.username}: ${message.content.content}`;
  messagesDiv.appendChild(messageDiv);
}
