"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader
import aiofiles

from .database import init_db
import asyncio
from .services import _start_global_gpu_collector, _stop_global_gpu_collector
from .api.workspaces import router as ws_router
from .api.instances import router as inst_router
from .api.configs import router as cfg_router
from .api.runtime import router as rt_router

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start global GPU collector (non-blocking)
    _start_global_gpu_collector()
    yield
    # Stop on shutdown
    _stop_global_gpu_collector()


app = FastAPI(title="Llama.cpp Manager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Templates - use Jinja2 Environment directly to avoid LRUCache bug
from jinja2 import Environment, FileSystemLoader
from starlette.templating import _TemplateResponse

_jinja_env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=True,
    cache_size=0,  # Disable cache
)
_jinja_env.add_extension("jinja2.ext.loopcontrols")

def get_template_response(name: str, context: dict):
    template = _jinja_env.get_template(name)
    return _TemplateResponse(template, context)

templates = type('Templates', (), {'TemplateResponse': staticmethod(get_template_response)})()

# API routes
app.include_router(ws_router)
app.include_router(inst_router)
app.include_router(cfg_router)
app.include_router(rt_router)

# ── Page routes (order matters: /config/new before /config/{cid}) ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/workspaces", response_class=HTMLResponse)
async def workspaces(request: Request):
    return templates.TemplateResponse("workspaces.html", {"request": request})


@app.get("/instances", response_class=HTMLResponse)
async def instances(request: Request):
    return templates.TemplateResponse("instances.html", {"request": request})


@app.get("/gpu", response_class=HTMLResponse)
async def gpu_page(request: Request):
    return templates.TemplateResponse("gpu.html", {"request": request})


@app.get("/models", response_class=HTMLResponse)
async def models_page(request: Request):
    return templates.TemplateResponse("models.html", {"request": request})


@app.get("/config/new", response_class=HTMLResponse)
async def config_new(request: Request, workspace_id: int = 0, instance_id: int = 0):
    return templates.TemplateResponse("config_form.html", {
        "request": request, "cid": 0, "workspace_id": workspace_id, "instance_id": instance_id
    })


@app.get("/config/{cid}", response_class=HTMLResponse)
async def config_detail(request: Request, cid: int):
    return templates.TemplateResponse("config_detail.html", {"request": request, "cid": cid})


@app.get("/config/{cid}/edit", response_class=HTMLResponse)
async def config_edit(request: Request, cid: int):
    return templates.TemplateResponse("config_form.html", {"request": request, "cid": cid})


@app.get("/config/{cid}/log", response_class=HTMLResponse)
async def config_log(request: Request, cid: int):
    return templates.TemplateResponse("config_log.html", {"request": request, "cid": cid})


@app.get("/config/{cid}/gpu", response_class=HTMLResponse)
async def config_gpu(request: Request, cid: int):
    return templates.TemplateResponse("config_gpu.html", {"request": request, "cid": cid})
