/* ==========================================================================
   BlinkChat — Join Room Page Logic (join.js)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("join-form");
  const codeInput = document.getElementById("room-code-input");
  const passwordInput = document.getElementById("room-password-input");
  const togglePwdBtn = document.getElementById("toggle-pwd-btn");
  const submitBtn = document.getElementById("join-submit-btn");
  const errorBox = document.getElementById("join-error");

  const scanQrBtn = document.getElementById("scan-qr-btn");
  const scannerBox = document.getElementById("scanner-box");
  const videoElem = document.getElementById("qr-video");
  const stopScanBtn = document.getElementById("stop-scan-btn");
  const scanStatus = document.getElementById("scan-status");

  let mediaStream = null;
  let scanAnimationId = null;

  // Auto-uppercase room code
  codeInput.addEventListener("input", () => {
    codeInput.value = codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  });

  // Toggle password visibility
  togglePwdBtn.addEventListener("click", () => {
    const isPassword = passwordInput.getAttribute("type") === "password";
    passwordInput.setAttribute("type", isPassword ? "text" : "password");
    togglePwdBtn.textContent = isPassword ? "🙈" : "👁";
  });

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
  }

  // Form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearError();

    const roomCode = codeInput.value.trim().toUpperCase();
    const roomPassword = passwordInput.value;

    if (!roomCode || !roomPassword) {
      showError("Please enter both the room code and password.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Verifying credentials...";

    try {
      const response = await fetch("/api/rooms/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_code: roomCode,
          room_password: roomPassword,
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error("Invalid room code or password.");
        } else if (response.status === 409) {
          throw new Error("This room is already full (maximum 2 participants).");
        } else if (response.status === 410) {
          throw new Error("This room has expired and is no longer accessible.");
        } else if (response.status === 429) {
          throw new Error("Too many join attempts. Please wait a minute and try again.");
        } else {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Unable to join room.");
        }
      }

      const data = await response.json();

      // Store minimal metadata in sessionStorage
      sessionStorage.setItem("blinkchat_room_code", roomCode);
      sessionStorage.setItem("blinkchat_slot", String(data.slot));
      sessionStorage.setItem("blinkchat_mode", data.mode);
      sessionStorage.setItem("blinkchat_expires_at", data.room_expires_at);

      // Stop camera if active
      stopCamera();

      // Navigate to chat
      window.location.href = "/chat";
    } catch (err) {
      showError(err.message || "An error occurred while joining.");
      submitBtn.disabled = false;
      submitBtn.textContent = "Join Securely";
    }
  });

  // QR Code Scanning using jsQR
  scanQrBtn.addEventListener("click", async () => {
    clearError();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showError("Camera access is not supported by your browser.");
      return;
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      videoElem.srcObject = mediaStream;
      videoElem.setAttribute("playsinline", "true");
      await videoElem.play();
      scannerBox.classList.remove("hidden");
      scanStatus.textContent = "Scanning for BlinkChat entry QR...";
      scanAnimationId = requestAnimationFrame(scanTick);
    } catch (err) {
      showError("Camera permission denied or camera unavailable: " + err.message);
      stopCamera();
    }
  });

  stopScanBtn.addEventListener("click", stopCamera);

  function stopCamera() {
    if (scanAnimationId) {
      cancelAnimationFrame(scanAnimationId);
      scanAnimationId = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    scannerBox.classList.add("hidden");
  }

  function scanTick() {
    if (videoElem.readyState === videoElem.HAVE_ENOUGH_DATA) {
      const canvas = document.createElement("canvas");
      canvas.width = videoElem.videoWidth;
      canvas.height = videoElem.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(videoElem, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

      if (window.jsQR) {
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: "dontInvert",
        });

        if (code && code.data) {
          scanStatus.textContent = "QR scanned! Valid BlinkChat entry link verified.";
          stopCamera();
          codeInput.focus();
          return;
        }
      }
    }
    scanAnimationId = requestAnimationFrame(scanTick);
  }
});
