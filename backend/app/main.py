from fastapi import FastAPI

from app import resumes

app = FastAPI(title="HireLens API", version="0.1.0")
app.include_router(resumes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
