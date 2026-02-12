import os
import threading

from fastapi import FastAPI


def _service_name() -> str:
    return (os.getenv("RAILWAY_SERVICE_NAME") or "").strip().lower()


def _build_mcp_server_app() -> FastAPI:
    """
    Railway is auto-starting this repo with: `uvicorn main:app ...`.
    For the MCP service we mount the FastMCP HTTP transport under /mcp.
    """

    from server import create_mcp

    mcp_server = create_mcp()
    mcp_asgi = mcp_server.http_app(path="/", transport="http")

    # FastMCP's HTTP transport requires its lifespan to be wired into the parent ASGI app.
    api = FastAPI(title="myxstack-mcp-server", lifespan=mcp_asgi.lifespan)
    api.mount("/mcp", mcp_asgi)

    @api.get("/")
    def root() -> dict:
        return {"ok": True, "service": "mcp-server"}

    return api


def _build_worker_app(kind: str) -> FastAPI:
    """
    For worker services (listener/dispatcher) we keep the container alive by
    running an ASGI app and starting the worker loop in a background thread.
    """

    api = FastAPI(title=f"myxstack-{kind}")

    @api.get("/")
    def root() -> dict:
        return {"ok": True, "service": kind}

    @api.get("/health")
    def health() -> dict:
        return {"ok": True}

    def _start_worker() -> None:
        if kind == "x-listener":
            from listener import main as run
        elif kind == "mcp-dispatcher":
            from mcp_dispatcher import main as run
        else:
            return

        thread = threading.Thread(target=run, name=f"{kind}-thread", daemon=True)
        thread.start()

    @api.on_event("startup")
    def _on_startup() -> None:
        _start_worker()

    return api


service = _service_name()

if service == "timeline-server":
    # Expose timeline API at the service root.
    from timeline_server import app as app  # noqa: F401
elif service == "mcp-server":
    app = _build_mcp_server_app()
elif service in {"x-listener", "mcp-dispatcher"}:
    app = _build_worker_app(service)
else:
    # Safe default for unknown service names.
    app = _build_worker_app(service or "unknown")
