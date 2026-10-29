# BlinkChat

BlinkChat is a private, real-time, two-person chat application built with FastAPI, WebSockets, SQLite, and vanilla modern JavaScript. It is designed for distraction-free, zero-knowledge two-party conversations with strict access control and two distinct operation modes: **Temporary Chat** (in-memory, zero disk persistence) and **Saved Chat** (encrypted/hashed persistence).

---

## Key Features

- **Strict Two-Person Limit**: Every room enforces exactly two participants (Slot 1 and Slot 2). Any third join attempt is rejected with HTTP 409 Conflict.
- **Dual Chat Modes**:
  - **Temporary Chat**: Messages exist exclusively in server memory during an active session. Zero messages are written to disk or database. Rooms expire automatically after inactivity or lifetime limit.
  - **Saved Chat**: Messages persist in the local database and can be reloaded across reconnects using paginated history.
- **Privacy-First Authentication**:
  - High-entropy 8-character room codes (uppercase alphanumeric).
  - Cryptographically generated 12-character passwords (Argon2id hashed, memory cost 64 MB).
  - Passwords are never stored in plaintext and never appear in URLs or server logs.
  - Creator enters room as Participant 1 directly after generation.
- **Secure QR Code Entry**:
  - QR codes encode **only** the generic entry URL (`/join`), never embedding room codes, passwords, or tokens.
  - Includes an integrated browser camera scanner powered by `jsQR`.
- **Session Security**:
  - HttpOnly, SameSite=Strict session cookies prevent XSS credential theft.
  - Tokens are SHA-256 hashed in the database.
  - WebSocket connections are authenticated before the connection upgrade.
- **Minimal, Responsive UI**:
  - Clean dark-mode interface with no third-party framework dependencies.
  - Strict DOM text-node rendering preventing script injection (XSS).

---

## Architecture & Project Structure

```
BlinkChat/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI API routers (health, rooms, ws)
│   │   ├── core/            # Configuration and Argon2id security helpers
│   │   ├── db/              # SQLAlchemy async engine, models, and init
│   │   ├── models/          # ORM models (Room, ParticipantSession, SavedMessage)
│   │   ├── schemas/         # Pydantic validation schemas
│   │   ├── services/        # Business logic & in-memory ConnectionManager
│   │   └── main.py          # FastAPI application factory and static mounts
│   ├── tests/               # Pytest automated test suite (27 tests)
│   └── pytest.ini           # Pytest configuration
├── frontend/
│   ├── index.html           # Landing page & room creation modal
│   ├── join.html            # Room join page with QR scanner
│   ├── chat.html            # Real-time WebSocket chat interface
│   ├── css/
│   │   └── style.css        # Responsive dark theme styling
│   ├── js/
│   │   ├── app.js           # Room creation and QR generation
│   │   ├── join.js          # Room joining & QR camera decoding
│   │   └── chat.js          # WebSocket messaging & UI rendering
│   └── assets/
│       └── logo.svg         # Application icon
├── blinkchat.db             # SQLite database file
├── requirements.txt         # Pinned Python dependencies
└── README.md
```

---

## Getting Started on Windows

### 1. Prerequisites
- Python 3.11+ (Python 3.13 tested)
- Existing virtual environment at `d:\Project\BlinkChat\.venv`

### 2. Verify / Install Dependencies
If activating the virtual environment manually:
```powershell
d:\Project\BlinkChat\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Launch BlinkChat
Start the Uvicorn ASGI server from the workspace root:
```powershell
d:\Project\BlinkChat\.venv\Scripts\uvicorn.exe app.main:app --app-dir d:\Project\BlinkChat\backend --host 127.0.0.1 --port 8000 --reload
```

Once started, open your browser to:
- **Landing & Create Room:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Join Room:** [http://127.0.0.1:8000/join](http://127.0.0.1:8000/join)
- **API Health:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Running the Automated Tests

### Pytest Unit & Integration Suite
To run all 27 unit and integration tests:
```powershell
Set-Location d:\Project\BlinkChat\backend
& "d:\Project\BlinkChat\.venv\Scripts\pytest.exe" tests\ -v
```

### End-to-End Live Verification Suite
To run the end-to-end integration suite verifying live HTTP, WebSocket bidirectional messaging, 2-person limit, zero persistence, and Argon2id hashing:
```powershell
& "d:\Project\BlinkChat\.venv\Scripts\python.exe" "C:\Users\subha\.gemini\antigravity\brain\c675a550-ec62-4ed4-a303-38147bae196d\scratch\run_live_test.py"
```

---

## Security Model Summary

| Concern | Implementation |
|---|---|
| Password Storage | Argon2id (`time_cost=2, memory_cost=65536, parallelism=2`) |
| Session Token | 256-bit cryptographic token (`secrets.token_urlsafe(32)`) |
| Session Storage | Stored in DB as SHA-256 hash; delivered via `HttpOnly`, `SameSite=Strict` cookie |
| QR Code Contents | Generic URL `/join` only; zero credentials or tokens in QR codes |
| Temporary Rooms | Zero disk or database persistence; stored in-memory in `ConnectionManager` |
| Saved Rooms | Messages stored in `saved_messages` table; paginated via authenticated cookie |
| XSS Mitigation | HTML escaping via `textContent` assignment; strict Content Security Policy |
| Clickjacking / MIME | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` |
| Rate Limiting | SlowAPI limiter on room creation (5/min) and room joining (10/min) |
