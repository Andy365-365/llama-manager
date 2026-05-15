# Llama Manager

Web 管理界面，用于管理 [llama.cpp](https://github.com/ggerganov/llama.cpp) 推理服务的启动、监控和配置。

[English](README.md) | 中文

## 功能特性

- **工作空间分组** — 将配置组织到不同的逻辑空间
- **运行参数配置** — 常用参数表单 + 高级自定义参数
- **进程管理** — 启动/停止/重启，自动检测 OOM/崩溃
- **GPU 资源监控** — nvidia-smi 图表化展示（利用率、显存、温度、功耗）
- **模型管理** — 扫描本地模型，查看元数据（参数量、量化格式、文件大小）
- **多实例支持** — 注册多个 llama.cpp 二进制文件（标准版、MTP 版等）
- **配置持久化** — SQLite 存储，支持导入/导出
- **实时日志** — SSE 流式传输，支持搜索过滤

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + Uvicorn |
| 前端 | Jinja2 模板 + HTMX + ECharts |
| 数据库 | SQLite (SQLAlchemy ORM) |
| 进程管理 | asyncio subprocess |
| GPU 监控 | nvidia-smi JSON 输出 |

## 快速开始

```bash
# 克隆
git clone https://github.com/Andy365-365/llama-manager.git
cd llama-manager

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动
./start.sh
```

浏览器访问 `http://localhost:7860`

## 环境要求

- Python 3.12+
- NVIDIA GPU + `nvidia-smi`（GPU 监控功能）
- 至少一个 llama.cpp 的 `llama-server` 二进制文件

## 项目结构

```
llama-manager/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── database.py          # SQLAlchemy 数据模型 + 数据库初始化
│   ├── services.py          # 核心服务（进程/GPU/模型）
│   └── api/
│       ├── workspaces.py    # 工作空间管理 API
│       ├── instances.py     # 推理框架实例 API
│       ├── configs.py       # 配置 CRUD API
│       └── runtime.py       # 运行时 API（启动/停止/日志/GPU）
├── templates/               # Jinja2 模板
│   ├── base.html            # 基础布局 + 导航栏
│   ├── dashboard.html       # 仪表盘
│   ├── config_form.html     # 配置编辑器
│   ├── config_detail.html   # 配置详情页
│   ├── config_log.html      # 日志查看器（SSE）
│   ├── workspaces.html      # 工作空间管理
│   ├── instances.html       # 推理框架管理
│   ├── gpu.html             # GPU 监控页面
│   └── models.html          # 模型管理
├── static/
│   ├── css/style.css        # 样式表
│   └── js/app.js            # 通用 JS 工具函数
├── data/                    # SQLite 数据库（已忽略）
├── logs/                    # 进程日志（已忽略）
├── start.sh                 # 启动脚本
└── requirements.txt         # Python 依赖
```

## API 端点

### 页面路由
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页 |
| GET | `/dashboard` | 仪表盘 |
| GET | `/config/new` | 新建配置 |
| GET | `/config/{cid}/edit` | 编辑配置 |
| GET | `/config/{cid}/log` | 查看日志 |
| GET | `/config/{cid}/gpu` | 配置 GPU 监控 |
| GET | `/workspaces` | 工作空间管理 |
| GET | `/instances` | 推理框架管理 |
| GET | `/gpu` | GPU 监控 |
| GET | `/models` | 模型扫描 |

### REST API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/workspaces/` | 工作空间 CRUD |
| GET/POST | `/api/instances/` | 推理框架实例管理 |
| POST | `/api/instances/auto-detect` | 自动检测 llama.cpp |
| GET/POST | `/api/configs/` | 配置 CRUD |
| GET/PUT/DELETE | `/api/configs/{cid}` | 配置操作 |
| POST | `/api/configs/{cid}/copy` | 复制配置 |
| GET | `/api/configs/export` | 导出配置 |
| POST | `/api/configs/import` | 导入配置 |
| POST | `/api/runtime/{cid}/start` | 启动配置 |
| POST | `/api/runtime/{cid}/stop` | 停止配置 |
| POST | `/api/runtime/{cid}/restart` | 重启配置 |
| GET | `/api/runtime/{cid}/log/tail` | 获取日志 |
| GET | `/api/runtime/{cid}/log/stream` | SSE 日志流 |
| GET | `/api/runtime/gpu/info` | GPU 实时信息 |
| GET | `/api/runtime/gpu/history` | GPU 历史数据 |
| GET | `/api/runtime/status/all` | 全部配置状态 |
| GET | `/api/runtime/models/scan` | 扫描模型 |

## 注意事项

- 模型文件路径必须存在，否则 llama-server 启动后会立即退出
- 端口冲突需用户自行处理
- 当前为局域网使用，无需认证

## License

MIT
