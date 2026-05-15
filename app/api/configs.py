"""Config CRUD + copy + import/export API."""
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.database import SessionLocal, Config, Workspace, LlamaInstance

router = APIRouter(prefix="/api/configs", tags=["configs"])


class ConfigCreate(BaseModel):
    workspace_id: int
    llama_instance_id: int
    name: str
    description: Optional[str] = None
    model_source: str = "path"
    model_path: str = ""
    ctx_size: Optional[int] = None
    gpu_layers: Optional[int] = None
    tensor_split: Optional[str] = None
    parallel: Optional[int] = None
    threads: Optional[int] = None
    threads_batch: Optional[int] = None
    batch_size: Optional[int] = None
    ubatch_size: Optional[int] = None
    flash_attn: Optional[str] = None
    cache_type_k: Optional[str] = None
    cache_type_v: Optional[str] = None
    cache_ram: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    api_key: Optional[str] = None
    jinja: Optional[bool] = None
    reasoning: Optional[str] = None
    mlock: Optional[bool] = None
    mmap: Optional[bool] = None
    log_timestamps: Optional[bool] = None
    metrics: Optional[bool] = None
    spec_type: Optional[str] = None
    spec_draft_n_max: Optional[int] = None
    spec_draft_p_min: Optional[float] = None
    split_mode: Optional[str] = None
    extra_args: str = ""


def _config_to_dict(c: Config) -> dict:
    d = {
        "id": c.id, "workspace_id": c.workspace_id,
        "llama_instance_id": c.llama_instance_id,
        "name": c.name, "description": c.description,
        "model_source": c.model_source, "model_path": c.model_path,
        "ctx_size": c.ctx_size, "gpu_layers": c.gpu_layers,
        "tensor_split": c.tensor_split, "parallel": c.parallel,
        "threads": c.threads, "threads_batch": c.threads_batch,
        "batch_size": c.batch_size, "ubatch_size": c.ubatch_size,
        "flash_attn": c.flash_attn,
        "cache_type_k": c.cache_type_k, "cache_type_v": c.cache_type_v,
        "cache_ram": c.cache_ram,
        "host": c.host, "port": c.port, "api_key": c.api_key,
        "jinja": c.jinja, "reasoning": c.reasoning,
        "mlock": c.mlock, "mmap": c.mmap,
        "log_timestamps": c.log_timestamps, "metrics": c.metrics,
        "spec_type": c.spec_type, "spec_draft_n_max": c.spec_draft_n_max,
        "spec_draft_p_min": c.spec_draft_p_min, "split_mode": c.split_mode,
        "extra_args": c.extra_args,
        "pid": c.pid, "status": c.status, "log_file": c.log_file,
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "workspace_name": c.workspace.name if c.workspace else "",
        "llama_instance_name": c.llama_instance.name if c.llama_instance else "",
    }
    return d


@router.get("/")
def list_configs(workspace_id: Optional[int] = None):
    db = SessionLocal()
    try:
        q = db.query(Config)
        if workspace_id:
            q = q.filter(Config.workspace_id == workspace_id)
        configs = q.order_by(Config.updated_at.desc()).all()
        return [_config_to_dict(c) for c in configs]
    finally:
        db.close()


@router.get("/{cid}")
def get_config(cid: int):
    db = SessionLocal()
    try:
        c = db.query(Config).filter(Config.id == cid).first()
        if not c:
            return {"ok": False, "error": "Not found"}
        return {"ok": True, **_config_to_dict(c)}
    finally:
        db.close()


@router.post("/")
def create_config(body: ConfigCreate):
    db = SessionLocal()
    try:
        # Validate workspace and instance exist
        ws = db.query(Workspace).filter(Workspace.id == body.workspace_id).first()
        if not ws:
            return {"ok": False, "error": "Workspace not found"}
        inst = db.query(LlamaInstance).filter(LlamaInstance.id == body.llama_instance_id).first()
        if not inst:
            return {"ok": False, "error": "Llama instance not found"}

        c = Config(**body.model_dump())
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"ok": True, "id": c.id}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.put("/{cid}")
def update_config(cid: int, body: ConfigCreate):
    db = SessionLocal()
    try:
        c = db.query(Config).filter(Config.id == cid).first()
        if not c:
            return {"ok": False, "error": "Not found"}

        # Don't allow changing workspace/instance while running
        if c.status == "running" or c.pid:
            safe_fields = {f for f in body.model_fields if f not in ("workspace_id", "llama_instance_id", "model_path", "port")}
            for f in safe_fields:
                val = getattr(body, f)
                if val is not None:
                    setattr(c, f, val)
        else:
            for f, val in body.model_dump().items():
                if val is not None:
                    setattr(c, f, val)

        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.delete("/{cid}")
def delete_config(cid: int):
    from app.services import stop_config, _stop_gpu_collector
    db = SessionLocal()
    try:
        c = db.query(Config).filter(Config.id == cid).first()
        if not c:
            return {"ok": False, "error": "Not found"}
        # Stop if running
        if c.pid:
            stop_config(cid)
        _stop_gpu_collector(cid)
        db.delete(c)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.post("/{cid}/copy")
def copy_config(cid: int, target_workspace_id: Optional[int] = None, new_name: Optional[str] = None):
    """Copy a config, optionally to another workspace."""
    db = SessionLocal()
    try:
        src = db.query(Config).filter(Config.id == cid).first()
        if not src:
            return {"ok": False, "error": "Source not found"}

        ws_id = target_workspace_id or src.workspace_id
        ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
        if not ws:
            return {"ok": False, "error": "Target workspace not found"}

        data = _config_to_dict(src)
        # Remove id and runtime fields
        for k in ("id", "pid", "status", "log_file", "started_at", "workspace_name", "llama_instance_name"):
            data.pop(k, None)
        data["workspace_id"] = ws_id
        data["name"] = new_name or f"{src.name} (copy)"

        c = Config(**data)
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"ok": True, "id": c.id, "name": c.name}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.get("/export")
def export_configs(workspace_id: Optional[int] = None):
    """Export configs as JSON."""
    db = SessionLocal()
    try:
        q = db.query(Config)
        if workspace_id:
            q = q.filter(Config.workspace_id == workspace_id)
        configs = q.all()
        data = []
        for c in configs:
            d = _config_to_dict(c)
            # Remove runtime fields
            for k in ("id", "pid", "status", "log_file", "started_at", "workspace_name", "llama_instance_name"):
                d.pop(k, None)
            data.append(d)
        return {"ok": True, "configs": data}
    finally:
        db.close()


class ImportBody(BaseModel):
    configs: list[dict]
    workspace_id: int


@router.post("/import")
def import_configs(body: ImportBody):
    """Import configs from JSON."""
    db = SessionLocal()
    try:
        ws = db.query(Workspace).filter(Workspace.id == body.workspace_id).first()
        if not ws:
            return {"ok": False, "error": "Workspace not found"}

        created = 0
        for item in body.configs:
            # Remove runtime fields
            for k in ("id", "pid", "status", "log_file", "started_at", "workspace_name", "llama_instance_name"):
                item.pop(k, None)
            item["workspace_id"] = body.workspace_id
            c = Config(**item)
            db.add(c)
            created += 1
        db.commit()
        return {"ok": True, "created": created}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
