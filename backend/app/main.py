from fastapi import FastAPI
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from app import auth, config, histories, resumes
from app.errors import add_error_handler, error_response

# Room for the multipart form around the file itself: boundaries, headers and
# the file name.
UPLOAD_FORM_OVERHEAD_BYTES = 64 * 1024


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

    @app.middleware("http")
    async def reject_large_uploads(request, call_next):
        # Turns away an upload that says it is over the limit before reading
        # any of it. The upload endpoint checks the file itself as well, for
        # requests that don't say how big they are.
        if request.method == "POST" and request.url.path == "/api/resumes":
            length = request.headers.get("content-length", "")
            if length.isdigit() and int(length) > config.MAX_UPLOAD_BYTES + UPLOAD_FORM_OVERHEAD_BYTES:
                return error_response(resumes.file_too_large())
        return await call_next(request)

    add_error_handler(app)
    app.include_router(resumes.router)
    app.include_router(histories.router)
    app.include_router(auth.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
