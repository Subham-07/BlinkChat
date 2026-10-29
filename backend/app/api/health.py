from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Simple health check. Does not expose configuration or secrets."""
    return {"status": "ok"}
