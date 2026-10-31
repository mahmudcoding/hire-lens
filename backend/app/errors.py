"""Errors with a machine-readable code next to the message (NFR-05 / DP-52).

Every error response has a "detail" with the message to show the candidate.
These also have a "code" the frontend can act on without reading the text,
plus any extra values that explain the error, such as the size limit.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class CodedError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, **extra: object) -> None:
        super().__init__(status_code, message)
        self.code = code
        self.extra = extra


def error_response(error: CodedError) -> JSONResponse:
    return JSONResponse(
        {"detail": error.detail, "code": error.code, **error.extra},
        status_code=error.status_code,
        headers=error.headers,
    )


def add_error_handler(app: FastAPI) -> None:
    @app.exception_handler(CodedError)
    async def coded_error(_request: Request, error: CodedError) -> JSONResponse:
        return error_response(error)
