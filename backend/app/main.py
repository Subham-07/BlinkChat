"""
BlinkChat FastAPI application.

Design decisions:
- Single SQLite file for MVP; switch DATABASE_URL to PostgreSQL for production.
- Session tokens are HttpOnly cookies; token hashes are stored in the DB.
- WebSocket connections are authenticated via session cookie before upgrade.
- In-memory connection manager is suitable for a single-worker deployment only.
- Cleanup task runs every 5 minutes to expire rooms.
- Database engine is initialised lazily in the lifespan to avoid event-loop
  conflicts on Windows during import time.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.db.base import init_engine, get_session_local
from app.db.init_db import init_db
from app.services.room_service import cleanup_expired_rooms
from app.api import rooms, ws, health
import pathlib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = pathlib.Path(__file__).parent.parent.parent / "frontend"


async def _cleanup_loop() -> None:
    """Background task: expire rooms every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        try:
            session_local = get_session_local()
            async with session_local() as db:
                await cleanup_expired_rooms(db)
        except Exception:
            logger.exception("Error during room cleanup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise the database engine inside the lifespan so it is created
    # within the running event loop (required on Windows with ProactorEventLoop).
    init_engine(settings.database_url)
    await init_db()
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="BlinkChat",
    description="Private two-person real-time chat",
    version="0.1.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — never allow wildcard with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' ws://127.0.0.1:8000 ws://localhost:8000;"
    )
    return response


# API routes
app.include_router(health.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(ws.router)

# Serve frontend static files
if FRONTEND_DIR.exists():
    css_dir = FRONTEND_DIR / "css"
    js_dir = FRONTEND_DIR / "js"
    assets_dir = FRONTEND_DIR / "assets"
    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/join")
    async def serve_join():
        return FileResponse(str(FRONTEND_DIR / "join.html"))

    @app.get("/chat")
    async def serve_chat():
        return FileResponse(str(FRONTEND_DIR / "chat.html"))
