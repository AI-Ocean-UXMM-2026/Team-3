import ipaddress
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from tools.backend_test_dashboard.runtime import Sandbox

STATIC = Path(__file__).parent / "static"
UUID_PATTERN = r"[0-9a-fA-F-]{36}"
ORDER = rf"/api/orders/{UUID_PATTERN}"
RIDER = rf"/api/riders/{UUID_PATTERN}"
ALLOWED = {
    "GET": [
        r"/api/session",
        r"/api/routes",
        r"/health",
        r"/api/orders",
        ORDER,
        ORDER + r"/(events|buyer-requests|assignments)",
        r"/api/riders",
        RIDER,
        RIDER + r"/queue",
    ],
    "POST": [
        r"/api/routes",
        rf"/api/routes/{UUID_PATTERN}/actions",
        ORDER + r"/(operations|prepare-assignment)",
        r"/api/orders/parse",
        r"/api/orders",
        r"/api/riders",
        ORDER + r"/(confirmation-link|confirmation-link/revoke|assign|unassign)",
    ],
    "PATCH": [
        ORDER,
        ORDER + r"/(status|assignment)",
        ORDER + rf"/buyer-requests/{UUID_PATTERN}",
        RIDER,
        RIDER + rf"/deliveries/{UUID_PATTERN}/status",
    ],
}
BUYER_METHODS = {
    "": "GET",
    "/verify": "POST",
    "/details": "GET",
    "/location": "PATCH",
    "/response": "PATCH",
}
PRIVATE_KEYS = {
    "access_token",
    "authorization",
    "development_token",
    "dev_access_token",
    "token_hash",
    "phone_binding",
    "confirmation_url",
    "absolute_url",
    "last_four",
}


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k.casefold() not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class ProxyCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["GET", "POST", "PATCH"]
    path: str = Field(min_length=1, max_length=500)
    body: dict | None = None
    actor: Literal["dispatcher", "rider"] = "dispatcher"
    rider_id: UUID | None = None
    buyer_handle: str | None = Field(default=None, max_length=100)


class ResetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal["RESET FICTIONAL DATA"]


class ExpiryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    buyer_handle: str = Field(max_length=100)
    kind: Literal["LINK", "SESSION"]


class StopBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal["STOP LOCAL TOOL"]


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_dashboard(origin="http://127.0.0.1:8765", *, sandbox_factory=Sandbox, frontend=None):
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or not parsed.port
    ):
        raise ValueError("Dashboard must use an exact http://127.0.0.1:PORT origin")

    @asynccontextmanager
    async def lifespan(app):
        app.state.sandbox = sandbox_factory()
        try:
            yield
        finally:
            app.state.sandbox.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    # Sessions never contain privileged credentials and are bounded for this single-user tool.
    app.state.sessions = {}

    @app.middleware("http")
    async def boundary(request, call_next):
        try:
            peer = ipaddress.ip_address(request.client.host)
            if not peer.is_loopback or request.headers.get("host") != parsed.netloc:
                return error(403, "LOCAL_ONLY", "Use the exact loopback dashboard URL.")
            if request.headers.get("origin", origin) != origin or request.headers.get(
                "sec-fetch-site"
            ) in {"cross-site", "same-site"}:
                return error(403, "ORIGIN_REJECTED", "Cross-origin dashboard access is disabled.")
            if request.url.path.startswith("/dashboard/"):
                key = request.cookies.get("lp_dashboard")
                session = app.state.sessions.get(key)
                if session is None or time.monotonic() - session["created"] > 8 * 3600:
                    return error(
                        401, "SESSION_REQUIRED", "Open the dashboard page to start a local session."
                    )
                request.state.owner = key
                if request.method != "GET" and not secrets.compare_digest(
                    request.headers.get("x-dashboard-csrf", ""), session["csrf"]
                ):
                    return error(
                        403, "CSRF_REJECTED", "Refresh the dashboard session before retrying."
                    )
                if request.method != "GET":
                    if request.headers.get("content-type", "").split(";")[0] != "application/json":
                        return error(415, "JSON_REQUIRED", "Send a JSON request.")
                    # Bound actual bytes, not just a caller-controlled Content-Length.
                    data = bytearray()
                    async for chunk in request.stream():
                        data.extend(chunk)
                        if len(data) > 65536:
                            return error(
                                413, "BODY_TOO_LARGE", "Dashboard requests are limited to 64 KiB."
                            )
                    request._body = bytes(data)
            response = await call_next(request)
        except Exception:
            # Do not print exception messages, payloads, cookies or capability URLs.
            response = error(
                500, "DASHBOARD_ERROR", "Local dashboard operation failed; no success was recorded."
            )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
                    "base-uri 'none'; form-action 'self'"
                ),
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error(
            422,
            "DASHBOARD_VALIDATION",
            "Invalid dashboard request. Check method, fields and JSON types.",
        )

    @app.get("/")
    def index(request: Request):
        key = request.cookies.get("lp_dashboard")
        if (
            key not in app.state.sessions
            or time.monotonic() - app.state.sessions[key]["created"] > 8 * 3600
        ):
            # Evict expired sessions; refuse unbounded browser session accumulation.
            now = time.monotonic()
            app.state.sessions = {
                k: v for k, v in app.state.sessions.items() if now - v["created"] <= 8 * 3600
            }
            if len(app.state.sessions) >= 32:
                return error(
                    429, "SESSION_LIMIT", "Restart this local tool to clear unused sessions."
                )
            key = secrets.token_urlsafe(32)
            app.state.sessions[key] = {"created": now, "csrf": secrets.token_urlsafe(32)}
        response = FileResponse((frontend or STATIC) / "index.html")
        response.set_cookie(
            "lp_dashboard", key, httponly=True, samesite="strict", max_age=8 * 3600, path="/"
        )
        return response

    @app.get("/assets/{name}")
    def asset(name: str):
        if name not in {"app.js", "style.css"}:
            return error(404, "NOT_FOUND", "Asset not found.")
        return FileResponse(STATIC / name)

    @app.get("/dashboard/bootstrap")
    def bootstrap(request: Request):
        with app.state.sandbox.lock:
            return {
                **app.state.sandbox.bootstrap(),
                "csrf": app.state.sessions[request.state.owner]["csrf"],
                "buyers": [
                    {"handle": key, "expires_at": value["expires_at"]}
                    for key, value in app.state.sandbox.buyers.items()
                    if value["owner"] == request.state.owner
                ],
            }

    @app.post("/dashboard/reset")
    def reset(body: ResetBody):
        if frontend is not None:
            return error(
                409,
                "PERSISTENT_WORKSPACE",
                "Persistent workspace reset is disabled; use isolated test runs.",
            )
        return app.state.sandbox.reset()

    @app.post("/dashboard/shutdown")
    def shutdown(body: StopBody):
        server = getattr(app.state, "server", None)
        if server is None:
            return error(
                409, "LAUNCHER_REQUIRED", "Use the dashboard launcher for graceful shutdown."
            )
        server.should_exit = True
        return {
            "stopping": True,
            "notice": "Local server is stopping and cleaning its temporary database.",
        }

    @app.post("/dashboard/expire")
    def expire(body: ExpiryBody, request: Request):
        box = app.state.sandbox
        with box.lock:
            if not box.expire(body.buyer_handle, request.state.owner, body.kind):
                return error(
                    404,
                    "BUYER_HANDLE_UNKNOWN",
                    "Select a buyer link created in this browser session.",
                )
            return {
                "test_fixture_only": True,
                "expired": body.kind,
                "notice": (
                    "Only this temporary fixture timestamp changed; "
                    "verify the result through the real buyer API."
                ),
            }

    @app.post("/dashboard/api")
    def proxy(body: ProxyCall, request: Request):
        box = app.state.sandbox
        with box.lock:
            parts = urlsplit(body.path)
            if (
                parts.scheme
                or parts.netloc
                or parts.fragment
                or "%" in parts.path
                or ".." in parts.path
                or "\\" in parts.path
            ):
                return error(
                    400, "PATH_REJECTED", "Only allowlisted application routes are accepted."
                )
            path, buyer = parts.path, None
            client, headers = box.dispatcher, {}
            if path.startswith("/api/confirm/@buyer"):
                suffix = path.removeprefix("/api/confirm/@buyer")
                if (
                    frontend is not None
                    and body.buyer_handle
                    and re.fullmatch(r"[A-Za-z0-9_-]{43}", body.buyer_handle)
                ):
                    # A buyer link is a public capability, not privileged development access.
                    # Keep each browser's verified authorization separate; reverify after restart.
                    buyer = box.workspace_buyers.setdefault(
                        (request.state.owner, body.buyer_handle),
                        {
                            "owner": request.state.owner,
                            "path": "/api/confirm/" + body.buyer_handle,
                        },
                    )
                else:
                    buyer = box.buyers.get(body.buyer_handle)
                if buyer is None or buyer["owner"] != request.state.owner:
                    return error(
                        404,
                        "BUYER_HANDLE_UNKNOWN",
                        "Generate or select a buyer link in this browser session.",
                    )
                if BUYER_METHODS.get(suffix) != body.method or parts.query:
                    return error(400, "PATH_REJECTED", "Unsupported buyer operation.")
                path = buyer["path"] + suffix
                client = box.public
                if buyer.get("authorization"):
                    headers["Authorization"] = "Bearer " + buyer["authorization"]
            elif not any(re.fullmatch(p, path) for p in ALLOWED[body.method]):
                return error(
                    400, "PATH_REJECTED", "This route is not available in the local testing proxy."
                )
            if body.actor == "rider":
                permitted = body.rider_id and (
                    (
                        body.method == "GET"
                        and path
                        in {f"/api/riders/{body.rider_id}/queue", "/api/session", "/api/routes"}
                    )
                    or (
                        body.method == "POST"
                        and re.fullmatch(rf"/api/routes/{UUID_PATTERN}/actions", path)
                    )
                    or (
                        body.method == "PATCH"
                        and re.fullmatch(
                            rf"/api/riders/{body.rider_id}/deliveries/{UUID_PATTERN}/status", path
                        )
                    )
                )
                client = box.rider_client(body.rider_id) if permitted else None
                if client is None:
                    return error(
                        403,
                        "RIDER_SCOPE",
                        "Choose an existing rider and their own queue/delivery route.",
                    )
            started = time.perf_counter()
            response = client.request(
                body.method,
                path + ("?" + parts.query if parts.query else ""),
                json=body.body,
                headers=headers,
            )
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            payload = response.json()
            if response.status_code == 201 and path.endswith("/confirmation-link"):
                handle = (
                    payload["confirmation_url"].rsplit("/", 1)[1]
                    if frontend is not None
                    else secrets.token_urlsafe(32)
                )
                box.buyers[handle] = {
                    "owner": request.state.owner,
                    "path": "/api" + payload["confirmation_url"],
                    "link_id": payload["link_id"],
                    "expires_at": payload["expires_at"],
                }
                if frontend is not None:
                    box.workspace_buyers[(request.state.owner, handle)] = box.buyers[handle].copy()
                payload = {
                    **scrub(payload),
                    "buyer_handle": handle,
                    "dashboard_url": "/#buyer=" + handle,
                    "notice": (
                        "Native buyer capability link: share only in the recipient's "
                        "trusted conversation. "
                        "Verification authorization remains server-side."
                        if frontend is not None
                        else (
                            "Private backend link held server-side; "
                            "this local test handle is session-bound."
                        )
                    ),
                }
            elif buyer is not None and path.endswith("/verify") and response.status_code == 200:
                buyer["authorization"] = payload["access_token"]
                payload = {
                    "verified": True,
                    "expires_at": payload["expires_at"],
                    "notice": (
                        "Buyer authorization held server-side, never returned to this browser."
                    ),
                }
            result = {
                "method": body.method,
                "endpoint": parts.path.replace("@buyer", "{token}"),
                "status": response.status_code,
                "duration_ms": elapsed,
                "ok": response.is_success,
                "data": scrub(payload),
            }
            out = JSONResponse(result, status_code=response.status_code)
            if "retry-after" in response.headers:
                out.headers["Retry-After"] = response.headers["retry-after"]
            return out

    if frontend is not None:
        from fastapi import HTTPException

        # Explicit first-party assets only: never serve backend, node_modules or private state.
        assets = {
            p.relative_to(frontend).as_posix(): p
            for p in frontend.rglob("*")
            if p.is_file()
            and p.suffix in {".html", ".css", ".js", ".mjs"}
            and not any(part in {"node_modules", "dist"} for part in p.parts)
            and ".test." not in p.name
            and not p.name.startswith("test-")
        }

        @app.get("/{filename:path}")
        def frontend_asset(filename: str):
            if filename not in assets:
                raise HTTPException(404, "Not found")
            path = assets[filename]
            return FileResponse(
                path, media_type="text/javascript" if path.suffix == ".mjs" else None
            )

    return app
