"""Serve only allowlisted UI assets; never expose backend source or data."""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[4]
FILES = {
    name: ROOT / name
    for name in (
        "api.html",
        "api.css",
        "api-model.mjs",
        "api-workspace.mjs",
        "styles.css",
        "functional.css",
        "index.html",
        "functional-app.js",
        "workflow-domain.js",
        "vendor/lannpya-order-parser.js",
        "extra.css",
        "interactions.css",
        "handoff.css",
        "delivery.css",
        "sw.js",
    )
}
FILES["lannpya-ai/docs/examples/lannpya-client.mjs"] = (
    ROOT / "lannpya-ai/docs/examples/lannpya-client.mjs"
)
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:*; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


def router():
    routes = APIRouter(include_in_schema=False)

    @routes.get("/")
    @routes.get("/confirm/{token}")
    def workspace(token: str | None = None):
        return FileResponse(FILES["api.html"], headers=HEADERS)

    @routes.get("/{filename:path}")
    def static_file(filename: str):
        path = FILES.get(filename)
        if path is None or not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(
            path, headers=HEADERS, media_type="text/javascript" if path.suffix == ".mjs" else None
        )

    return routes
