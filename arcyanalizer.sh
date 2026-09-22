#!/bin/bash
cd "/Users/arcy/Documents/ClaudeCode/arcyanalizer" || exit 1
(sleep 1.5 && open "http://127.0.0.1:54321") &
exec ./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
