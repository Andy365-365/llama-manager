#!/bin/bash
# Start Llama.cpp Manager
cd /data/llama-manager
source venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
