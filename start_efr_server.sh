#!/bin/bash
# Start the EFR server from the project root
export PYTHONPATH=src
exec uvicorn src.efr_server.main:app --reload --port 8001 