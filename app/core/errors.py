from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    detail = "bad request"

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        *,
        headers: dict[str, str] | None = None,
        extra: dict | None = None,
    ):
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        self.headers = headers
        self.extra = extra or {}


class FieldErrorsError(AppError):
    def __init__(self, field_errors: list[dict[str, str]]):
        super().__init__(detail="validation failed")
        self.field_errors = field_errors


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
            field_errors.append(
                {"field": loc or "body", "message": err.get("msg", "invalid")}
            )
        return JSONResponse(
            status_code=400, content={"detail": {"field_errors": field_errors}}
        )

    @app.exception_handler(FieldErrorsError)
    async def field_errors_handler(
        request: Request, exc: FieldErrorsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"field_errors": exc.field_errors}},
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        content: dict = {"detail": exc.detail}
        if exc.extra:
            content.update(exc.extra)
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=exc.headers,
        )
