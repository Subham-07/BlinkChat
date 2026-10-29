/* ==========================================================================
   BlinkChat — WebSocket Real-Time Chat Client (chat.js)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const messagesContainer = document.getElementById("messages-container");
  const emptyState = document.getElementById("empty-state");
  const composerForm = document.getElementById("composer-form");
  const composerInput = document.getElementById("composer-input");
  const charCounter = document.getElementById("char-counter");
  const sendBtn = document.getElementById("send-btn");
  const connDot = document.getElementById("conn-dot");
  const connStatusText = document.getElementById("conn-status-text");
  const participantsCount = document.getElementById("participants-count");
  const leaveRoomBtn = document.getElementById("leave-room-btn");
  const modeBadge = document.getElementById("chat-mode-badge");

  // Read stored session data
  const mySlot = parseInt(sessionStorage.getItem("blinkchat_slot") || "0", 10);
  const roomMode = sessionStorage.getItem("blinkchat_mode") || "temporary";

  // Setup UI mode badge
  if (modeBadge) {
    if (roomMode === "saved") {
      modeBadge.textContent = "Saved Chat";
      modeBadge.className = "mode-badge mode-badge-saved";
    } else {
      modeBadge.textContent = "Temporary";
      modeBadge.className = "mode-badge mode-badge-temp";
    }
  }

  // WebSocket connection & retry state
  let socket = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const backoffDelays = [1000, 2000, 4000, 8000, 16000];
  let isExplicitLeave = false;

  function getWsUrl() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws`;
  }

  function setStatus(status, text) {
    connDot.className = "status-dot";
    if (status === "connected") {
      connDot.classList.add("connected");
      connStatusText.textContent = text || "Connected";
    } else if (status === "disconnected") {
      connDot.classList.add("disconnected");
      connStatusText.textContent = text || "Disconnected";
    } else {
      connStatusText.textContent = text || "Connecting...";
    }
  }

  function connect() {
    if (isExplicitLeave) return;

    setStatus("connecting", "Connecting...");
    socket = new WebSocket(getWsUrl());

    socket.onopen = () => {
      reconnectAttempts = 0;
      setStatus("connected", "Connected");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleIncomingMessage(data);
      } catch (err) {
        console.error("Error parsing message payload:", err);
      }
    };

    socket.onclose = (event) => {
      if (isExplicitLeave) return;

      if (event.code === 4001) {
        // Unauthorized session
        setStatus("disconnected", "Session Expired");
        alert("Your session has expired or is invalid. Please join again.");
        window.location.href = "/join";
        return;
      }

      if (event.code === 4003) {
        setStatus("disconnected", "Origin Not Allowed");
        return;
      }

      setStatus("disconnected", "Connection lost");

      if (reconnectAttempts < maxReconnectAttempts) {
        const delay = backoffDelays[reconnectAttempts] || 16000;
        reconnectAttempts++;
        connStatusText.textContent = `Reconnecting (${reconnectAttempts}/${maxReconnectAttempts})...`;
        setTimeout(connect, delay);
      } else {
        connStatusText.textContent = "Disconnected (Failed to reconnect)";
      }
    };

    socket.onerror = (err) => {
      console.warn("WebSocket error:", err);
    };
  }

  // Message dispatcher
  function handleIncomingMessage(data) {
    if (data.type === "message") {
      renderChatMessage(data.slot, data.content, data.sent_at);
    } else if (data.type === "history") {
      if (Array.isArray(data.messages)) {
        data.messages.forEach((m) => renderChatMessage(m.slot, m.content, m.sent_at));
      }
    } else if (data.type === "system") {
      handleSystemMessage(data.text);
    } else if (data.type === "error") {
      renderSystemNotice(data.text, "error");
    }
  }

  function handleSystemMessage(text) {
    if (!text) return;
    if (text.startsWith("participants:")) {
      const count = text.split(":")[1];
      participantsCount.textContent = `${count}/2 online`;
    } else {
      renderSystemNotice(text, "info");
    }
  }

  // Safe DOM Rendering — strict textContent to prevent XSS
  function renderChatMessage(slot, content, sentAt) {
    if (emptyState && !emptyState.classList.contains("hidden")) {
      emptyState.classList.add("hidden");
    }

    const row = document.createElement("div");
    row.className = "message-row " + (slot === mySlot ? "own" : "other");

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    // Text content MUST use textContent
    const textNode = document.createElement("span");
    textNode.textContent = content;
    bubble.appendChild(textNode);

    // Timestamp
    const meta = document.createElement("span");
    meta.className = "message-meta";
    let formattedTime = "";
    if (sentAt) {
      try {
        const d = new Date(sentAt);
        formattedTime = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      } catch (e) {
        formattedTime = "";
      }
    }
    const senderLabel = slot === mySlot ? "You" : `User ${slot}`;
    meta.textContent = `${senderLabel} · ${formattedTime}`;
    bubble.appendChild(meta);

    row.appendChild(bubble);
    messagesContainer.appendChild(row);

    // Scroll to latest message
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function renderSystemNotice(text, level) {
    const row = document.createElement("div");
    row.className = "system-message-row";

    const pill = document.createElement("span");
    pill.className = "system-pill";
    pill.textContent = text;
    if (level === "error") {
      pill.style.color = "var(--danger)";
    }
    row.appendChild(pill);
    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Composer events
  composerInput.addEventListener("input", () => {
    // Character counter
    const len = composerInput.value.length;
    charCounter.textContent = `${len} / 4000`;

    // Auto-grow textarea
    composerInput.style.height = "auto";
    composerInput.style.height = Math.min(composerInput.scrollHeight, 160) + "px";
  });

  composerInput.addEventListener("keydown", (e) => {
    // Enter sends message, Shift+Enter adds newline
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      composerForm.dispatchEvent(new Event("submit"));
    }
  });

  composerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = composerInput.value.trim();
    if (!content) return;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      alert("Chat is not connected. Please wait for reconnection.");
      return;
    }

    try {
      const payload = JSON.stringify({ type: "message", content: content });
      socket.send(payload);
      composerInput.value = "";
      composerInput.style.height = "auto";
      charCounter.textContent = "0 / 4000";
      composerInput.focus();
    } catch (err) {
      console.error("Failed to send message:", err);
    }
  });

  // Leave Room
  leaveRoomBtn.addEventListener("click", () => {
    if (confirm("Are you sure you want to leave this chat room?")) {
      isExplicitLeave = true;
      if (socket) {
        socket.close();
      }
      sessionStorage.clear();
      window.location.href = "/";
    }
  });

  // Initial connect
  connect();
});
