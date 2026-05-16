"""Database setup and models."""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, Boolean, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "llama_manager.db")
os.path.dirname(DB_PATH)  # ensure dir exists

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Workspace(Base):
    """Logical grouping for configs."""
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(String(512), default="")
    created_at = Column(DateTime, default=datetime.now)

    configs = relationship("Config", back_populates="workspace", cascade="all, delete-orphan")


class LlamaInstance(Base):
    """Registered llama.cpp installation."""
    __tablename__ = "llama_instances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    install_path = Column(String(512), nullable=False)  # e.g. /llama.cpp-mtp
    server_binary = Column(String(512), nullable=False)  # e.g. /llama.cpp-mtp/build/bin/llama-server
    description = Column(String(512), default="")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    configs = relationship("Config", back_populates="llama_instance")


class Config(Base):
    """A runnable configuration."""
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    llama_instance_id = Column(Integer, ForeignKey("llama_instances.id"), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(String(512), default="")

    # Model
    model_source = Column(String(16), nullable=False, default="path")  # "path" or "hf"
    model_path = Column(String(1024), default="")  # local path or HF repo:id

    # Parameters
    ctx_size = Column(Integer, nullable=True)
    gpu_layers = Column(Integer, nullable=True)
    tensor_split = Column(String(256), nullable=True)  # e.g. "58,42"
    parallel = Column(Integer, nullable=True)
    threads = Column(Integer, nullable=True)
    threads_batch = Column(Integer, nullable=True)
    batch_size = Column(Integer, nullable=True)
    ubatch_size = Column(Integer, nullable=True)
    flash_attn = Column(String(16), nullable=True)  # on/off/auto
    cache_type_k = Column(String(16), nullable=True)
    cache_type_v = Column(String(16), nullable=True)
    cache_ram = Column(String(16), nullable=True)  # "0" means all
    host = Column(String(64), nullable=True)
    port = Column(Integer, nullable=True)
    api_key = Column(String(256), nullable=True)
    jinja = Column(Boolean, nullable=True)
    reasoning = Column(String(16), nullable=True)  # on/off/auto
    mlock = Column(Boolean, nullable=True)
    mmap = Column(Boolean, nullable=True)
    log_timestamps = Column(Boolean, nullable=True)
    metrics = Column(Boolean, nullable=True)
    spec_type = Column(String(32), nullable=True)  # mtp, none
    spec_draft_n_max = Column(Integer, nullable=True)
    spec_draft_p_min = Column(Float, nullable=True)
    split_mode = Column(String(32), nullable=True)  # layer, row

    # Advanced: free-form extra args
    extra_args = Column(Text, default="")

    # Runtime state
    pid = Column(Integer, nullable=True, default=None)
    status = Column(String(16), default="stopped")  # stopped/starting/running/stopped_error
    log_file = Column(String(512), nullable=True)
    started_at = Column(DateTime, nullable=True)

    workspace = relationship("Workspace", back_populates="configs")
    llama_instance = relationship("LlamaInstance", back_populates="configs")
    gpu_metrics = relationship("GpuMetric", back_populates="config", cascade="all, delete-orphan")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GpuMetric(Base):
    """GPU metric snapshot."""
    __tablename__ = "gpu_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=True)
    gpu_index = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    utilization_gpu = Column(Float, nullable=True)
    utilization_memory = Column(Float, nullable=True)
    memory_used = Column(Float, nullable=True)       # MB
    memory_total = Column(Float, nullable=True)      # MB
    temperature = Column(Float, nullable=True)        # Celsius
    power_usage = Column(Float, nullable=True)        # Watts
    power_limit = Column(Float, nullable=True)        # Watts
    fan_speed = Column(Float, nullable=True)          # percent

    config = relationship("Config", back_populates="gpu_metrics", foreign_keys=[config_id])


def init_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)
