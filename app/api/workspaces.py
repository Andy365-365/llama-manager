"""Workspace CRUD API."""
from fastapi import APIRouter
from pydantic import BaseModel
from app.database import SessionLocal, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: str
    description: str = ""


@router.get("/")
def list_workspaces():
    db = SessionLocal()
    try:
        ws = db.query(Workspace).order_by(Workspace.created_at.desc()).all()
        result = []
        for w in ws:
            configs = []
            for c in w.configs:
                configs.append({
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "status": c.status,
                    "pid": c.pid,
                    "port": c.port,
                    "model_path": c.model_path,
                    "llama_instance_name": c.llama_instance.name if c.llama_instance else "",
                    "llama_instance_id": c.llama_instance_id,
                    "workspace_id": c.workspace_id,
                    "model_source": c.model_source,
                    "ctx_size": c.ctx_size,
                    "gpu_layers": c.gpu_layers,
                    "parallel": c.parallel,
                    "threads": c.threads,
                    "tensor_split": c.tensor_split,
                    "extra_args": c.extra_args,
                })
            result.append({
                "id": w.id, "name": w.name, "description": w.description,
                "config_count": len(configs), "created_at": w.created_at.isoformat(),
                "configs": configs,
            })
        return result
    finally:
        db.close()


@router.post("/")
def create_workspace(body: WorkspaceCreate):
    db = SessionLocal()
    try:
        w = Workspace(name=body.name, description=body.description)
        db.add(w)
        db.commit()
        db.refresh(w)
        return {"ok": True, "id": w.id, "name": w.name}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.put("/{wid}")
def update_workspace(wid: int, body: WorkspaceUpdate):
    db = SessionLocal()
    try:
        w = db.query(Workspace).filter(Workspace.id == wid).first()
        if not w:
            return {"ok": False, "error": "Not found"}
        w.name = body.name
        w.description = body.description
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.delete("/{wid}")
def delete_workspace(wid: int):
    db = SessionLocal()
    try:
        w = db.query(Workspace).filter(Workspace.id == wid).first()
        if not w:
            return {"ok": False, "error": "Not found"}
        db.delete(w)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
