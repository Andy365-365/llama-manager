"""Core services: process management, GPU monitoring, model scanning."""
import os
import re
import csv
import io
import json
import asyncio
import subprocess
import shutil
from datetime import datetime
from typing import Optional
import psutil

from .database import SessionLocal, Config, GpuMetric, LlamaInstance

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Active GPU collectors: set of config_ids to monitor
_active_collectors: set[int] = set()
_gpu_collector_task: Optional[asyncio.Task] = None


# ── Process Management ──────────────────────────────────────────

def _build_command(config: Config) -> list[str]:
    """Build llama-server command from config."""
    cmd = [config.llama_instance.server_binary]

    # Model
    if config.model_source == "hf":
        cmd.extend(["-hf", config.model_path])
    else:
        cmd.extend(["-m", config.model_path])

    # Common params
    if config.ctx_size is not None:
        cmd.extend(["--ctx-size", str(config.ctx_size)])
    if config.gpu_layers is not None:
        cmd.extend(["--gpu-layers", str(config.gpu_layers)])
    if config.tensor_split:
        cmd.extend(["--tensor-split", config.tensor_split])
    if config.parallel is not None:
        cmd.extend(["--parallel", str(config.parallel)])
    if config.threads is not None:
        cmd.extend(["-t", str(config.threads)])
    if config.threads_batch is not None:
        cmd.extend(["--threads-batch", str(config.threads_batch)])
    if config.batch_size is not None:
        cmd.extend(["--batch-size", str(config.batch_size)])
    if config.ubatch_size is not None:
        cmd.extend(["--ubatch-size", str(config.ubatch_size)])
    if config.flash_attn:
        cmd.extend(["--flash-attn", config.flash_attn])
    if config.cache_type_k:
        cmd.extend(["--cache-type-k", config.cache_type_k])
    if config.cache_type_v:
        cmd.extend(["--cache-type-v", config.cache_type_v])
    if config.cache_ram is not None:
        cmd.extend(["--cache-ram", str(config.cache_ram)])
    if config.host:
        cmd.extend(["--host", config.host])
    if config.port:
        cmd.extend(["--port", str(config.port)])
    if config.api_key:
        cmd.extend(["--api-key", config.api_key])
    if config.jinja is not None:
        cmd.append("--jinja" if config.jinja else "--no-jinja")
    if config.reasoning:
        cmd.extend(["--reasoning", config.reasoning])
    if config.mlock:
        cmd.append("--mlock")
    if config.mmap is not None:
        cmd.append("--mmap" if config.mmap else "--no-mmap")
    if config.log_timestamps:
        cmd.append("--log-timestamps")
    if config.metrics:
        cmd.append("--metrics")
    if config.spec_type:
        cmd.extend(["--spec-type", config.spec_type])
    if config.spec_draft_n_max is not None:
        cmd.extend(["--spec-draft-n-max", str(config.spec_draft_n_max)])
    if config.spec_draft_p_min is not None:
        cmd.extend(["--spec-draft-p-min", str(config.spec_draft_p_min)])
    if config.split_mode:
        cmd.extend(["--split-mode", config.split_mode])

    # Extra args
    if config.extra_args:
        cmd.extend(config.extra_args.split())

    return cmd


def _log_file_path(config_id: int) -> str:
    return os.path.join(LOGS_DIR, f"config_{config_id}.log")


def start_config(config_id: int) -> dict:
    """Start llama-server for a config. Returns status dict."""
    db = SessionLocal()
    try:
        config = db.query(Config).filter(Config.id == config_id).first()
        if not config:
            return {"ok": False, "error": "Config not found"}

        # Check already running
        if config.pid and _is_running(config.pid):
            return {"ok": False, "error": f"Already running (PID {config.pid})"}

        # Check port conflict
        if config.port and _port_in_use(config.port):
            return {"ok": False, "error": f"Port {config.port} is already in use"}

        cmd = _build_command(config)
        log_path = _log_file_path(config_id)

        # Truncate log file
        with open(log_path, "w") as f:
            f.write(f"[{datetime.now().isoformat()}] Starting: {' '.join(cmd)}\n")
            f.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=open(log_path, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        config.pid = proc.pid
        config.status = "starting"
        config.log_file = log_path
        config.started_at = datetime.now()
        db.commit()

        # Start GPU collector
        _start_gpu_collector(config_id)

        return {"ok": True, "pid": proc.pid, "log_file": log_path}
    finally:
        db.close()


def stop_config(config_id: int) -> dict:
    """Stop llama-server for a config."""
    db = SessionLocal()
    try:
        config = db.query(Config).filter(Config.id == config_id).first()
        if not config or not config.pid:
            return {"ok": False, "error": "Not running"}

        pid = config.pid
        if _is_running(pid):
            try:
                os.kill(pid, 15)  # SIGTERM
                # Wait up to 5s
                for _ in range(50):
                    if not _is_running(pid):
                        break
                    import time
                    time.sleep(0.1)
                else:
                    os.kill(pid, 9)  # SIGKILL
            except ProcessLookupError:
                pass

        config.pid = None
        config.status = "stopped"
        config.started_at = None
        db.commit()

        # Stop GPU collector
        _stop_gpu_collector(config_id)

        return {"ok": True}
    finally:
        db.close()


def restart_config(config_id: int) -> dict:
    """Restart a config."""
    stop_config(config_id)
    import time
    time.sleep(1)
    return start_config(config_id)


def update_status(config_id: int) -> dict:
    """Update running status from actual process state."""
    db = SessionLocal()
    try:
        config = db.query(Config).filter(Config.id == config_id).first()
        if not config:
            return {"ok": False, "error": "Config not found"}

        if config.pid and not _is_running(config.pid):
            config.pid = None
            config.status = "stopped"
            config.started_at = None
            _stop_gpu_collector(config_id)
            db.commit()

        return {"ok": True, "status": config.status, "pid": config.pid}
    finally:
        db.close()


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _port_in_use(port: int) -> bool:
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


# ── GPU Monitoring ──────────────────────────────────────────────

async def _master_gpu_collector():
    """Single background task that collects GPU metrics for all active configs."""
    while True:
        for cid in list(_active_collectors):
            try:
                _collect_gpu_snapshot(cid)
            except Exception:
                pass
        await asyncio.sleep(5.0)


def _start_gpu_collector(config_id: int, interval: float = 5.0):
    _active_collectors.add(config_id)


def _stop_gpu_collector(config_id: int):
    _active_collectors.discard(config_id)


def _collect_gpu_snapshot(config_id: int):
    """Run nvidia-smi and save metrics."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,utilization.memory,memory.used,memory.total,"
                "temperature.gpu,power.draw,power.limit,fan.speed",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return

        db = SessionLocal()
        try:
            reader = csv.reader(io.StringIO(result.stdout.strip()))
            for row in reader:
                if len(row) < 9:
                    continue
                try:
                    m = GpuMetric(
                        config_id=config_id,
                        gpu_index=int(row[0]),
                        timestamp=datetime.now(),
                        utilization_gpu=float(row[1]),
                        utilization_memory=float(row[2]),
                        memory_used=float(row[3]),
                        memory_total=float(row[4]),
                        temperature=float(row[5]),
                        power_usage=float(row[6]),
                        power_limit=float(row[7]),
                        fan_speed=float(row[8]),
                    )
                    db.add(m)
                except (ValueError, IndexError):
                    continue
            db.commit()
        finally:
            db.close()
    except FileNotFoundError:
        pass  # nvidia-smi not found


def get_gpu_metrics(config_id: int, minutes: int = 30, gpu_index: Optional[int] = None) -> list[dict]:
    """Query GPU metrics for a config."""
    db = SessionLocal()
    try:
        from datetime import timedelta
        since = datetime.now() - timedelta(minutes=minutes)
        q = db.query(GpuMetric).filter(
            GpuMetric.config_id == config_id,
            GpuMetric.timestamp >= since
        )
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
                "fan_speed": m.fan_speed,
            }
            for m in metrics
        ]
    finally:
        db.close()


def get_gpu_count() -> int:
    """Get number of GPUs."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split("\n"))
    except FileNotFoundError:
        pass
    return 0


def get_gpu_info() -> list[dict]:
    """Get current GPU info."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,"
                "temperature.gpu,power.draw,fan.speed",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return []

        gpus = []
        reader = csv.reader(io.StringIO(result.stdout.strip()))
        for row in reader:
            if len(row) < 9:
                continue
            try:
                gpus.append({
                    "index": int(row[0]),
                    "name": row[1].strip(),
                    "utilization_gpu": float(row[2]),
                    "utilization_memory": float(row[3]),
                    "memory_used": float(row[4]),
                    "memory_total": float(row[5]),
                    "temperature": float(row[6]),
                    "power_draw": float(row[7]),
                    "fan_speed": float(row[8]),
                })
            except (ValueError, IndexError):
                continue
        return gpus
    except FileNotFoundError:
        return []


# ── Model Scanning ──────────────────────────────────────────────

def scan_models(directories: Optional[list[str]] = None) -> list[dict]:
    """Scan directories for GGUF model files."""
    if directories is None:
        directories = [
            os.path.expanduser("~/.cache/llama-cpp/models"),
            os.path.expanduser("~/models"),
            "/data/models",
        ]

    models = []
    for d in directories:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".gguf"):
                    full_path = os.path.join(root, f)
                    size = os.path.getsize(full_path)
                    models.append({
                        "path": full_path,
                        "name": f,
                        "size_bytes": size,
                        "size_human": _human_size(size),
                        "dir": root,
                        "metadata": _parse_model_name(f),
                    })
    return models


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _parse_model_name(filename: str) -> dict:
    """Extract quant, params, etc from filename."""
    info = {"filename": filename}

    # Quant patterns: Q4_K_M, Q5_K_S, Q8_0, Q4_0, etc.
    qmatch = re.search(r'(Q\d[_\-]?[A-Z0-9]*)', filename)
    if qmatch:
        info["quant"] = qmatch.group(1)

    # Params: 7B, 13B, 70B, etc.
    pmatch = re.search(r'(\d+(?:\.\d+)?)B', filename, re.IGNORECASE)
    if pmatch:
        info["params"] = pmatch.group(1) + "B"

    return info


# ── Log helpers ──────────────────────────────────────────────────

def tail_log(config_id: int, lines: int = 100) -> str:
    """Get last N lines of log file."""
    log_path = _log_file_path(config_id)
    if not os.path.exists(log_path):
        return ""
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), log_path],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception:
        return ""


def search_log(config_id: int, pattern: str) -> str:
    """Search log file with grep."""
    log_path = _log_file_path(config_id)
    if not os.path.exists(log_path):
        return ""
    try:
        result = subprocess.run(
            ["grep", "-i", "--color=never", pattern, log_path],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout if result.returncode == 0 else "No matches found."
    except Exception:
        return "Search error."
