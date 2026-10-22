"""Serve Supabase-authenticated Signboard and its API. Run behind HTTPS in production."""

import json

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings
from app.db.session import BACKEND_ROOT
from app.main import create_app


def application():
    settings = Settings()
    if not settings.supabase_auth_enabled or not settings.order_management_enabled:
        raise ValueError(
            "Enable Supabase Auth and order management before starting the secure server"
        )
    if (
        settings.environment == "production"
        and not settings.database_url.get_secret_value().startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        )
    ):
        raise ValueError("Production requires an explicit PostgreSQL database URL")
    frontend = BACKEND_ROOT.parent / "frontend" / "dist"
    if not (frontend / "index.html").is_file():
        raise ValueError("Run npm run build before starting the secure server")
    app = create_app(settings)

    @app.get("/runtime-config.js")
    def runtime_config():
        body = (
            "globalThis.LANNPYA_RUNTIME="
            + json.dumps(
                {
                    "mode": "SUPABASE_BACKEND",
                    "supabaseUrl": settings.supabase_url,
                    "supabaseKey": settings.supabase_publishable_key,
                }
            )
            + ";globalThis.LANNPYA_RUNTIME.apiBase=location.origin;"
        )
        return Response(body, media_type="text/javascript", headers={"Cache-Control": "no-store"})

    @app.get("/maps-config.js")
    def maps_config():
        return Response(
            "globalThis.LANNPYA_MAPS="
            + json.dumps({"googleKey": settings.google_maps_browser_key or ""})
            + ";",
            media_type="text/javascript",
        )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=()"
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
