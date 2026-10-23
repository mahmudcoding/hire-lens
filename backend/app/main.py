from fastapi import FastAPI
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app import auth, config, histories, resumes


def create_app() -> FastAPI:
    app = FastAPI(title="HireLens API", version="0.1.0")

    if config.FORCE_HTTPS:
        # Redirects any plain HTTP request to HTTPS (NFR-01 / DP-19). Needs a
        # real TLS certificate in front of the app to mean anything - see DP-34.
        app.add_middleware(HTTPSRedirectMiddleware)

    @app.middleware("http")
    async def add_hsts_header(request, call_next):
        response = await call_next(request)
        if config.FORCE_HTTPS:
            # Tells the browser to use HTTPS for a year, even if a link or a
            # typed URL says http://, so a stray http:// link can't
            # downgrade a later visit either.
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    app.include_router(resumes.router)
    app.include_router(histories.router)
    app.include_router(auth.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
