import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app import config, resumes
from app.storage import get_storage


async def _cleanup_loop(interval_seconds: float) -> None:
    """Delete resumes older than 24 hours, repeating every interval_seconds (DP-29)."""
    storage_factory = app.dependency_overrides.get(get_storage, get_storage)
    while True:
        await asyncio.sleep(interval_seconds)
        storage_factory().delete_expired()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_cleanup_loop(config.CLEANUP_INTERVAL_SECONDS))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="HireLens API", version="0.1.0", lifespan=lifespan)
app.include_router(resumes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
