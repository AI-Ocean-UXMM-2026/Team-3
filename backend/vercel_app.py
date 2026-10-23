"""Vercel API service; the web service serves the built frontend separately."""

import json

from fastapi.responses import Response

from app.core.config import Settings
from app.db.session import normalize_database_url
from app.main import create_app


def application(settings=None, database=None):
    settings = settings or Settings()
    if not settings.supabase_auth_enabled or not settings.order_management_enabled:
        raise ValueError("Hosted workspace requires Supabase authentication and order management")
    if (
        normalize_database_url(settings.database_url.get_secret_value()).get_backend_name()
        != "postgresql"
    ):
        raise ValueError("Hosted workspace requires persistent PostgreSQL")
    api = create_app(settings, database=database)

    @api.get("/runtime-config.js", include_in_schema=False)
    def runtime_config():
        public = {
            "mode": "SUPABASE_BACKEND",
            "supabaseUrl": settings.supabase_url,
            "supabaseKey": settings.supabase_publishable_key,
        }
        return Response(
            "globalThis.LANNPYA_RUNTIME="
            + json.dumps(public)
            + ";globalThis.LANNPYA_RUNTIME.apiBase=location.origin;",
            media_type="text/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @api.get("/maps-config.js", include_in_schema=False)
    def maps_config():
        return Response(
            "globalThis.LANNPYA_MAPS="
            + json.dumps({"googleKey": settings.google_maps_browser_key or ""})
            + ";",
            media_type="text/javascript",
            headers={"Cache-Control": "no-store"},
        )

    return api


app = application()
