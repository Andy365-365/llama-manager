"""Runtime API: start/stop/restart, logs, GPU metrics, models."""
import os
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import time

from app.services import (
    start_config, stop_config, restart_config, update_status,
    tail_log, search_log, get_gpu_metrics, get_gpu_count, get_gpu_info,
    scan_models, _start_gpu_collector, _stop_gpu_collector,
    _log_file_path,
)
from app.database import SessionLocal, Config, GpuMetric
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.post("/{cid}/start")
def api_start(cid: int):
    return start_config(cid)


@router.post("/{cid}/stop")
def api_stop(cid: int):
    return stop_config(cid)


@router.post("/{cid}/restart")
def api_restart(cid: int):
    return restart_config(cid)


@router.post("/{cid}/status")
def api_status(cid: int):
    return update_status(cid)


@router.get("/status/all")
def api_all_status():
    """Get status of all configs."""
    db = SessionLocal()
    try:
        configs = db.query(Config).all()
        result = []
        for c in configs:
            if c.pid:
                import os as _os
                running = False
                try:
                    _os.kill(c.pid, 0)
                    running = True
                except (OSError, ProcessLookupError):
                    pass
                if not running:
                    c.pid = None
                    c.status = "stopped"
                    c.started_at = None
                    _stop_gpu_collector(c.id)
                    db.commit()
                else:
                    c.status = "running"
            result.append({
                "id": c.id, "name": c.name, "status": c.status,
                "pid": c.pid, "port": c.port,
                "workspace_name": c.workspace.name if c.workspace else "",
            })
        return result
    finally:
        db.close()


# ── Log streaming via SSE ──────────────────────────────────────

@router.get("/{cid}/log/stream")
async def log_stream(cid: int):
    """Server-sent events: stream new log lines as they appear."""
    log_path = _log_file_path(cid)

    async def event_generator():
        if not os.path.exists(log_path):
            yield f"data: [No log file yet]\n\n"
            return

        # Start from end of file
        size = os.path.getsize(log_path)
        with open(log_path, "r") as f:
            f.seek(size)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}"
                else:
                    await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{cid}/log/tail")
def api_tail_log(cid: int, lines: int = 100):
    return {"log": tail_log(cid, lines)}


@router.post("/{cid}/log/search")
def api_search_log(cid: int, pattern: str):
    return {"result": search_log(cid, pattern)}


# ── GPU Metrics ─────────────────────────────────────────────────

@router.get("/gpu/history")
def api_gpu_history(minutes: int = 30, gpu_index: Optional[int] = None):
    """Get GPU history metrics (global, not tied to a config)."""
    db = SessionLocal()
    try:
        since = datetime.now() - timedelta(minutes=minutes)
        q = db.query(GpuMetric).filter(GpuMetric.timestamp >= since)
        if gpu_index is not None:
            q = q.filter(GpuMetric.gpu_index == gpu_index)
        q = q.order_by(GpuMetric.timestamp)
        metrics = q.all()
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "gpu_index": m.gpu_index,
                "utilization_gpu": m.utilization_gpu,
                "utilization_memory": m.utilization_memory,
                "memory_used": m.memory_used,
                "memory_total": m.memory_total,
                "temperature": m.temperature,
                "power_usage": m.power_usage,
            }
            for m in metrics
        ]
    finally:
        db.close()


@router.get("/gpu/metrics/{cid}")
def api_gpu_metrics(cid: int, minutes: int = 30, gpu_index: Optional[int] = None):
    return get_gpu_metrics(cid, minutes, gpu_index)


@router.get("/gpu/info")
def api_gpu_info():
    return {"count": get_gpu_count(), "gpus": get_gpu_info()}


@router.post("/gpu/snapshot")
def api_gpu_snapshot():
    """Force a one-time GPU snapshot."""
    from app.services import _collect_gpu_snapshot
    # Collect for all running configs
    db = SessionLocal()
    try:
        running = db.query(Config).filter(Config.pid.isnot(None)).all()
        for c in running:
            _collect_gpu_snapshot(c.id)
        return {"ok": True, "collected": len(running)}
    finally:
        db.close()


# ── Model scanning ──────────────────────────────────────────────

class ScanRequest(BaseModel):
    directories: Optional[list[str]] = None


@router.get("/models/directories")
def api_model_directories():
    """List available directories for model scanning (with existence status)."""
    candidates = [
        os.path.expanduser("~/.cache/llama-cpp/models"),
        os.path.expanduser("~/models"),
        "/data/models",
        "/data/llm",
        "/models",
        "/root/models",
    ]
    result = []
    for d in candidates:
        exists = os.path.isdir(d)
        # Count .gguf files if exists
        count = 0
        if exists:
            for root, _, files in os.walk(d):
                count += sum(1 for f in files if f.endswith('.gguf'))
        result.append({"path": d, "exists": exists, "model_count": count})
    return result


@router.post("/models/scan")
def api_scan_models(body: Optional[ScanRequest] = None):
    dirs = body.directories if body else None
    return scan_models(dirs)


@router.get("/models/scan")
def api_scan_models_get(directories: Optional[str] = None):
    """Scan models. directories: comma-separated paths."""
    dirs = [d.strip() for d in directories.split(",")] if directories else None
    return scan_models(dirs)
