# Llama Manager

Web UI for managing [llama.cpp](https://github.com/ggerganov/llama.cpp) inference services — launch, monitor, and configure multiple instances from a single dashboard.

English | [中文](README.zh.md)

## Features

- **Workspace grouping** — organize configs into logical workspaces
- **Run configuration** — common parameters form + advanced custom args
- **Process management** — start/stop/restart with OOM/crash detection
- **GPU monitoring** — real-time nvidia-smi charts (utilization, VRAM, temperature, power)
- **Model management** — scan local models, view metadata (params, quantization, size)
- **Multi-instance support** — register multiple llama.cpp binaries (standard, MTP, etc.)
- **Persistent config** — SQLite storage with import/export
- **Live logs** — SSE streaming with search/filter

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| Frontend | Jinja2 templates + HTMX + ECharts |
| Database | SQLite (SQLAlchemy ORM) |
| Process mgmt | asyncio subprocess |
| GPU monitoring | nvidia-smi JSON output |

## Quick Start

```bash
# Clone
git clone https://github.com/Andy365-365/llama-manager.git
cd llama-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start
./start.sh
```

Open `http://localhost:7860` in your browser.

## Prerequisites

- Python 3.12+
- NVIDIA GPU + `nvidia-smi` (for GPU monitoring)
- One or more `llama-server` binaries from llama.cpp

## Project Structure

```
llama-manager/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # SQLAlchemy models + DB init
│   ├── services.py          # Core services (process/GPU/model)
│   └── api/
│       ├── workspaces.py    # Workspace CRUD API
│       ├── instances.py     # llama.cpp instance API
│       ├── configs.py       # Config CRUD API
│       └── runtime.py       # Runtime API (start/stop/logs/GPU)
├── templates/               # Jinja2 templates
│   ├── base.html            # Base layout + navigation
│   ├── dashboard.html       # Dashboard
│   ├── config_form.html     # Config editor
│   ├── config_detail.html   # Config detail view
│   ├── config_log.html      # Log viewer (SSE)
│   ├── workspaces.html      # Workspace management
│   ├── instances.html       # Inference framework mgmt
│   ├── gpu.html             # GPU monitoring page
│   └── models.html          # Model management
├── static/
│   ├── css/style.css        # Styles
│   └── js/app.js            # Shared JS utilities
├── data/                    # SQLite database (gitignored)
├── logs/                    # Process logs (gitignored)
├── start.sh                 # Launch script
└── requirements.txt         # Python dependencies
```

## API Endpoints

### Pages
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Home page |
| GET | `/dashboard` | Dashboard |
| GET | `/config/new` | New config |
| GET | `/config/{cid}/edit` | Edit config |
| GET | `/config/{cid}/log` | View logs |
| GET | `/config/{cid}/gpu` | Config GPU monitoring |
| GET | `/workspaces` | Workspace management |
| GET | `/instances` | Inference framework mgmt |
| GET | `/gpu` | GPU monitoring |
| GET | `/models` | Model management |

### REST API
| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/workspaces/` | Workspace CRUD |
| GET/POST | `/api/instances/` | Inference framework mgmt |
| POST | `/api/instances/auto-detect` | Auto-detect llama.cpp |
| GET/POST | `/api/configs/` | Config CRUD |
| GET/PUT/DELETE | `/api/configs/{cid}` | Config operations |
| POST | `/api/configs/{cid}/copy` | Copy config |
| GET | `/api/configs/export` | Export configs |
| POST | `/api/configs/import` | Import configs |
| POST | `/api/runtime/{cid}/start` | Start config |
| POST | `/api/runtime/{cid}/stop` | Stop config |
| POST | `/api/runtime/{cid}/restart` | Restart config |
| GET | `/api/runtime/{cid}/log/tail` | Get logs |
| GET | `/api/runtime/{cid}/log/stream` | SSE log stream |
| GET | `/api/runtime/gpu/info` | GPU real-time info |
| GET | `/api/runtime/gpu/history` | GPU history |
| GET | `/api/runtime/status/all` | All config statuses |
| GET | `/api/runtime/models/scan` | Scan models |

## License

MIT
