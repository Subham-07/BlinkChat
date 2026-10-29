/* ==========================================================================
   BlinkChat — Landing Page Logic (app.js)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("create-modal");
  const openModalBtns = [
    document.getElementById("header-create-btn"),
    document.getElementById("hero-create-btn"),
  ];
  const closeModalBtn = document.getElementById("close-modal-btn");
  const createStep = document.getElementById("modal-create-step");
  const resultStep = document.getElementById("modal-result-step");
  const confirmCreateBtn = document.getElementById("confirm-create-btn");
  const createError = document.getElementById("create-error");
  const enterRoomBtn = document.getElementById("enter-room-btn");

  const labelTemp = document.getElementById("label-temp");
  const labelSaved = document.getElementById("label-saved");
  const modeInputs = document.querySelectorAll('input[name="room-mode"]');

  let currentCreatedRoom = null;

  // Toggle radio card styling
  modeInputs.forEach((input) => {
    input.addEventListener("change", () => {
      if (input.value === "temporary") {
        labelTemp.classList.add("active");
        labelSaved.classList.remove("active");
      } else {
        labelSaved.classList.add("active");
        labelTemp.classList.remove("active");
      }
    });
  });

  // Modal open / close
  function openModal() {
    createStep.classList.remove("hidden");
    resultStep.classList.add("hidden");
    createError.classList.add("hidden");
    createError.textContent = "";
    confirmCreateBtn.disabled = false;
    confirmCreateBtn.textContent = "Generate Room Credentials";
    modal.classList.remove("hidden");
  }

  function closeModal() {
    modal.classList.add("hidden");
  }

  openModalBtns.forEach((btn) => {
    if (btn) btn.addEventListener("click", openModal);
  });

  if (closeModalBtn) {
    closeModalBtn.addEventListener("click", closeModal);
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  // Room Creation API call
  confirmCreateBtn.addEventListener("click", async () => {
    const selectedMode = document.querySelector('input[name="room-mode"]:checked').value;
    confirmCreateBtn.disabled = true;
    confirmCreateBtn.textContent = "Generating...";
    createError.classList.add("hidden");

    try {
      const response = await fetch("/api/rooms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: selectedMode }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to create room.");
      }

      const data = await response.json();
      currentCreatedRoom = data;

      // Populate result UI
      document.getElementById("display-room-code").textContent = data.room_code;
      document.getElementById("display-room-password").textContent = data.room_password;
      document.getElementById("display-room-mode").textContent = data.mode;

      // Generate QR Code — ONLY encoding generic /join URL
      const qrCanvas = document.getElementById("qr-canvas");
      const joinUrl = window.location.origin + "/join";

      if (window.QRCode && QRCode.toCanvas) {
        QRCode.toCanvas(qrCanvas, joinUrl, {
          width: 160,
          margin: 1,
          color: { dark: "#1A1A2E", light: "#FFFFFF" },
        }, (err) => {
          if (err) console.error("QR Code error:", err);
        });
      }

      createStep.classList.add("hidden");
      resultStep.classList.remove("hidden");
    } catch (err) {
      createError.textContent = err.message || "An unexpected error occurred.";
      createError.classList.remove("hidden");
      confirmCreateBtn.disabled = false;
      confirmCreateBtn.textContent = "Generate Room Credentials";
    }
  });

  // Copy buttons
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetId = btn.getAttribute("data-target");
      const targetElem = document.getElementById(targetId);
      if (!targetElem) return;

      const text = targetElem.textContent.trim();
      try {
        await navigator.clipboard.writeText(text);
        const originalText = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => {
          btn.textContent = originalText;
        }, 1500);
      } catch (err) {
        // Fallback selection
        const range = document.createRange();
        range.selectNodeContents(targetElem);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
    });
  });

  // Enter Room button for creator
  enterRoomBtn.addEventListener("click", async () => {
    if (!currentCreatedRoom) return;
    enterRoomBtn.disabled = true;
    enterRoomBtn.textContent = "Entering room...";

    try {
      // Creator joins to obtain session cookie & slot 1
      const response = await fetch("/api/rooms/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_code: currentCreatedRoom.room_code,
          room_password: currentCreatedRoom.room_password,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Could not join created room.");
      }

      const joinData = await response.json();
      // Store minimal metadata in sessionStorage (NEVER password or auth token)
      sessionStorage.setItem("blinkchat_room_code", currentCreatedRoom.room_code);
      sessionStorage.setItem("blinkchat_slot", String(joinData.slot));
      sessionStorage.setItem("blinkchat_mode", joinData.mode);
      sessionStorage.setItem("blinkchat_expires_at", joinData.room_expires_at);

      window.location.href = "/chat";
    } catch (err) {
      alert("Error joining room: " + err.message);
      enterRoomBtn.disabled = false;
      enterRoomBtn.textContent = "Enter Room as Participant 1";
    }
  });
});
