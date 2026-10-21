import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException

from app.ai.base import AddressProvider, AIProviderError
from app.ai.extraction import AddressExtractionProvider
from app.ai.factory import create_extraction_provider, create_provider
from app.api.buyer_confirmation import protected_router, public_router
from app.api.order_management import router as order_router
from app.api.riders import router as rider_router
from app.api.routes import router
from app.api.workflow import router as workflow_router
from app.core.access_logging import install_access_filter
from app.core.config import Settings
from app.core.order_errors import OrderAPIError
from app.db.session import Database
from app.parsing.places import LocationCatalog
from app.services.buyer_policy import TownshipBoundaryResolver

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": details or []},
        },
    )


def create_app(
    settings: Settings | None = None,
    provider: AddressProvider | None = None,
    location_catalog: LocationCatalog | None = None,
    extraction_provider: AddressExtractionProvider | None = None,
    database: Database | None = None,
    township_boundaries: TownshipBoundaryResolver | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    own_database = database is None
    active_database = None
    if settings.order_management_enabled and settings.environment in {"local", "test"}:
        active_database = (
            database if database is not None else Database(settings.database_url.get_secret_value())
        )

    @asynccontextmanager
    async def lifespan(application):
        try:
            yield
        finally:
            if own_database and active_database is not None:
                active_database.dispose()

    install_access_filter()
    application = FastAPI(
        title="LannPya AI",
        version="0.7.0",
        description="Rules-first parsing and local-only persistent order management.",
        lifespan=lifespan,
    )
    application.state.address_provider = (
        provider if provider is not None else create_provider(settings)
    )
    application.state.parser_mode = settings.parser_mode
    application.state.settings = settings
    application.state.database = active_database
    application.state.township_boundaries = (
        township_boundaries if township_boundaries is not None else TownshipBoundaryResolver()
    )
    application.state.extraction_provider = (
        extraction_provider
        if extraction_provider is not None
        else create_extraction_provider(settings)
    )
    application.state.location_catalog = (
        location_catalog if location_catalog is not None else LocationCatalog()
    )

    @application.middleware("http")
    async def no_order_caching(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            # Catch at the ASGI boundary so Uvicorn cannot log private exception text.
            logger.error("Unhandled backend error: %s", type(exc).__name__)
            response = error_response(500, "INTERNAL_ERROR", "An unexpected server error occurred.")
        if request.url.path.startswith(
            (
                "/api/orders",
                "/api/users",
                "/api/confirm",
                "/api/riders",
                "/api/routes",
                "/api/session",
            )
        ):
            response.headers["Cache-Control"] = "no-store"
        if request.url.path.startswith("/api/confirm"):
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
            response.headers["X-Content-Type-Options"] = "nosniff"
        if response.status_code == 429:
            response.headers["Retry-After"] = "60"
        return response

    # Wrap sanitized exception responses too, so browser clients can read their JSON.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Dev-Access-Token", "Authorization"],
        expose_headers=["Retry-After"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Omit input values and context: malformed orders can contain personal data.
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed.",
            [
                {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
                for item in exc.errors()
            ],
        )

    @application.exception_handler(AIProviderError)
    async def provider_error(request: Request, exc: AIProviderError):
        logger.warning("Address provider failed")
        return error_response(
            502, "AI_PROVIDER_ERROR", "Address provider could not process the request."
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        response = error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        # Record exception type only; exception messages may contain customer data.
        logger.error("Unhandled backend error: %s", type(exc).__name__)
        return error_response(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    @application.exception_handler(OrderAPIError)
    async def order_error(request: Request, exc: OrderAPIError):
        return error_response(exc.status, exc.code, exc.message)

    @application.exception_handler(StaleDataError)
    async def stale_order(request: Request, exc: StaleDataError):
        return error_response(
            409, "VERSION_CONFLICT", "Order changed; retrieve the latest version before updating."
        )

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        logger.warning("Database integrity conflict")
        return error_response(409, "DATABASE_CONFLICT", "The change conflicts with stored data.")

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.warning("Database operation failed")
        return error_response(
            503, "DATABASE_UNAVAILABLE", "Database operation could not be completed."
        )

    application.include_router(router)
    application.include_router(order_router)
    application.include_router(protected_router)
    application.include_router(public_router)
    application.include_router(rider_router)
    application.include_router(workflow_router)
    return application


app = create_app()
