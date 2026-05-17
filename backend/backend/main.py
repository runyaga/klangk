"""Bark backend: FastAPI app with HTTP + WebSocket endpoints."""

import logging
import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import auth, container_manager, file_service, user_store, workspace_manager
from .ws_handler import handle_websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _seed_default_user() -> None:
    """Create default user if it doesn't exist."""
    import bcrypt
    username = os.environ.get("BARK_DEFAULT_USER", "admin")
    password = os.environ.get("BARK_DEFAULT_PASSWORD", "admin")
    existing = await user_store.get_user_by_username(username)
    if existing is None:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        await user_store.create_user(username, password_hash)
        logger.info("Created default user '%s'", username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await user_store.init_db()
    await _seed_default_user()
    container_manager.start_cleanup_loop()
    logger.info("Bark backend started")
    yield
    await container_manager.shutdown()
    logger.info("Bark backend stopped")


app = FastAPI(title="Bark", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Config endpoint ---

SOLIPLEX_URL = os.environ.get("SOLIPLEX_URL", "")

@app.get("/api/config")
async def get_config():
    return {"soliplex_url": SOLIPLEX_URL}


# --- Auth endpoints ---

@app.post("/auth/register", response_model=auth.TokenResponse)
async def register(req: auth.RegisterRequest):
    return await auth.register(req)


@app.post("/auth/login", response_model=auth.TokenResponse)
async def login(req: auth.LoginRequest):
    return await auth.login(req)


@app.post("/auth/logout")
async def logout(user: dict = Depends(auth.get_current_user)):
    # Stop all user containers
    await container_manager.stop_user_containers(user["id"])
    # Note: token invalidation happens via blocklist in auth.logout()
    # but we need the raw token here — handled in middleware or manually
    return {"status": "ok"}


# --- Workspace endpoints ---

@app.get("/workspaces")
async def list_workspaces(user: dict = Depends(auth.get_current_user)):
    return await workspace_manager.list_workspaces(user["id"])


@app.post("/workspaces")
async def create_workspace(name: str, user: dict = Depends(auth.get_current_user)):
    try:
        return await workspace_manager.create_workspace(user["id"], name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, user: dict = Depends(auth.get_current_user)):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Stop and remove container if running
    if workspace.get("container_id"):
        await container_manager.remove_container(workspace["container_id"])

    deleted = await workspace_manager.delete_workspace(workspace_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted"}


# --- Message history endpoints ---

@app.get("/workspaces/{workspace_id}/messages")
async def get_messages(workspace_id: str, user: dict = Depends(auth.get_current_user)):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await user_store.get_messages(workspace_id)


# --- File endpoints ---

@app.get("/workspaces/{workspace_id}/files")
async def list_files(
    workspace_id: str,
    path: str = ".",
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return file_service.list_files(user["id"], workspace_id, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/workspaces/{workspace_id}/files/content")
async def read_file(
    workspace_id: str,
    path: str,
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        content = file_service.read_file(user["id"], workspace_id, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if content is None:
        raise HTTPException(status_code=404, detail="File not found or too large")
    return {"path": path, "content": content}


@app.delete("/workspaces/{workspace_id}/files")
async def delete_file(
    workspace_id: str,
    path: str,
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        deleted = file_service.delete_path(user["id"], workspace_id, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"path": deleted, "status": "deleted"}


@app.post("/workspaces/{workspace_id}/files/rename")
async def rename_file(
    workspace_id: str,
    old_path: str,
    new_path: str,
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        renamed = file_service.rename_path(user["id"], workspace_id, old_path, new_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Destination already exists")
    return {"path": renamed, "status": "renamed"}


@app.get("/workspaces/{workspace_id}/files/download")
async def download_file(
    workspace_id: str,
    path: str,
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        resolved = file_service.resolve_path(user["id"], workspace_id, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if resolved.is_file():
        return FileResponse(resolved, filename=resolved.name)
    # Directory: zip it on the fly
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in resolved.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(resolved))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{resolved.name}.zip"'},
    )


@app.post("/workspaces/{workspace_id}/files/upload")
async def upload_file(
    workspace_id: str,
    file: UploadFile,
    path: str = "",
    user: dict = Depends(auth.get_current_user),
):
    workspace = await workspace_manager.get_workspace(workspace_id, user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    filename = path if path else file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    try:
        saved_path = file_service.write_file(user["id"], workspace_id, filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"path": saved_path, "status": "uploaded"}



# --- Hosted app proxy ---

import httpx

_proxy_client: httpx.AsyncClient | None = None


async def _get_proxy_client() -> httpx.AsyncClient:
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = httpx.AsyncClient(follow_redirects=True)
    return _proxy_client


@app.api_route(
    "/hosted/{workspace_id}/{port:int}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_hosted_app(
    workspace_id: str,
    port: int,
    path: str,
    request: Request,
):
    """Proxy requests to apps running in workspace containers (no auth required)."""
    # Build upstream URL
    upstream_url = f"http://127.0.0.1:{port}/{path}"
    logger.info("Proxying %s %s -> %s", request.method, request.url.path, upstream_url)
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    # Proxy the request (streaming)
    client = await _get_proxy_client()
    body = await request.body()
    try:
        req = client.build_request(
            method=request.method,
            url=upstream_url,
            headers={
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "authorization", "connection")
            },
            content=body if body else None,
        )
        resp = await client.send(req, stream=True)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="App is not running on this port")
    except httpx.RemoteProtocolError:
        raise HTTPException(status_code=502, detail="App did not send a valid response")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="App did not respond in time")

    # Forward response headers, excluding hop-by-hop
    excluded = {"transfer-encoding", "connection", "keep-alive"}
    headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    async def stream_body():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()

    return StreamingResponse(
        content=stream_body(),
        status_code=resp.status_code,
        headers=headers,
    )


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await handle_websocket(ws)


# --- Static files (Flutter Web) ---
# Must be last so API routes take priority

from starlette.middleware import Middleware
from starlette.responses import Response

_frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "build" / "web"
if _frontend_dir.exists():
    _static_app = StaticFiles(directory=str(_frontend_dir), html=True)

    @app.middleware("http")
    async def add_no_cache_headers(request, call_next):
        response = await call_next(request)
        # Add no-cache headers for HTML and JS files served from frontend
        if request.url.path.endswith((".html", ".js")) or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.mount("/", _static_app, name="frontend")
