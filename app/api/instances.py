"""Llama.cpp instance management API."""
import os
from fastapi import APIRouter
from pydantic import BaseModel
from app.database import SessionLocal, LlamaInstance

router = APIRouter(prefix="/api/instances", tags=["llama-instances"])


class InstanceCreate(BaseModel):
    name: str
    install_path: str
    description: str = ""


class InstanceUpdate(BaseModel):
    name: str
    install_path: str
    description: str = ""


@router.get("/")
def list_instances():
    db = SessionLocal()
    try:
        instances = db.query(LlamaInstance).order_by(LlamaInstance.created_at.desc()).all()
        result = []
        for inst in instances:
            exists = os.path.isfile(inst.server_binary)
            result.append({
                "id": inst.id, "name": inst.name,
                "install_path": inst.install_path, "server_binary": inst.server_binary,
                "description": inst.description, "is_default": inst.is_default,
                "binary_exists": exists,
                "config_count": len(inst.configs),
            })
        return result
    finally:
        db.close()


@router.post("/")
def create_instance(body: InstanceCreate):
    db = SessionLocal()
    try:
        binary = os.path.join(body.install_path, "build", "bin", "llama-server")
        if not os.path.isfile(binary):
            return {"ok": False, "error": f"llama-server not found at {binary}"}

        # If this is the first instance or marked default, set is_default
        existing = db.query(LlamaInstance).count()
        is_default = existing == 0

        inst = LlamaInstance(
            name=body.name, install_path=body.install_path,
            server_binary=binary, description=body.description, is_default=is_default
        )
        db.add(inst)
        db.commit()
        db.refresh(inst)
        return {"ok": True, "id": inst.id, "name": inst.name}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.put("/{iid}")
def update_instance(iid: int, body: InstanceUpdate):
    db = SessionLocal()
    try:
        inst = db.query(LlamaInstance).filter(LlamaInstance.id == iid).first()
        if not inst:
            return {"ok": False, "error": "Not found"}
        binary = os.path.join(body.install_path, "build", "bin", "llama-server")
        if not os.path.isfile(binary):
            return {"ok": False, "error": f"llama-server not found at {binary}"}
        inst.name = body.name
        inst.install_path = body.install_path
        inst.server_binary = binary
        inst.description = body.description
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.delete("/{iid}")
def delete_instance(iid: int):
    db = SessionLocal()
    try:
        inst = db.query(LlamaInstance).filter(LlamaInstance.id == iid).first()
        if not inst:
            return {"ok": False, "error": "Not found"}
        db.delete(inst)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.post("/{iid}/set-default")
def set_default(iid: int):
    db = SessionLocal()
    try:
        db.query(LlamaInstance).update({"is_default": False})
        inst = db.query(LlamaInstance).filter(LlamaInstance.id == iid).first()
        if not inst:
            return {"ok": False, "error": "Not found"}
        inst.is_default = True
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@router.post("/auto-detect")
def auto_detect():
    """Auto-detect llama.cpp installations in common locations."""
    candidates = [
        "/llama.cpp", "/llama.cpp-mtp",
        os.path.expanduser("~/.unsloth/llama.cpp"),
        "/opt/llama.cpp",
    ]
    found = []
    for path in candidates:
        binary = os.path.join(path, "build", "bin", "llama-server")
        if os.path.isfile(binary):
            name = os.path.basename(path)
            found.append({"name": name, "install_path": path, "server_binary": binary})
    return found
