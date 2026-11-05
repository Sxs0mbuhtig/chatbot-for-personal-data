#!/usr/bin/env bash

# ==============================================================================
# km_lexicon Systemd & Environment Setup Script
# Target: Automate directory creation, python environment setup, and systemd deployment.
# ==============================================================================

set -euo pipefail

# Configuration Parameters
BASE_DIR="${HOME}/km_lexicon_engine"
CONF_DIR="${BASE_DIR}/my_Apps"
SCRIPTS_DIR="${BASE_DIR}/scripts"
LOGS_DIR="${BASE_DIR}/logs"
SERVICE_NAME="km-lexicon-batch"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "======================================================================"
echo "Initializing km_lexicon Infrastructure & Background Service Setup"
echo "======================================================================"

# 1. Create Directory Hierarchy
echo "[1/5] Creating directory structure..."
mkdir -p "${CONF_DIR}" "${SCRIPTS_DIR}" "${LOGS_DIR}" "${SYSTEMD_USER_DIR}"

# 2. Deploy Configuration File
echo "[2/5] Deploying Antigravity Rules Configuration..."
cat << 'EOF' > "${CONF_DIR}/km_lexicon_antigravity_rules.md"
# Antigravity 2.0 & Local MCP Pool Execution Rules (km_lexicon Optimized)

## Critical Mandate: Hard Sub-1% Cloud Token Budget
1. Stateless Orchestrator Mode: Route via HAProxy http://127.0.0.1:11435
2. Low Offload Thresholds: Code >5 lines, Prose >20 words -> local Ollama pool.
3. Keep Cloud API response bodies under 30 words total per turn.
EOF

# 3. Deploy Python Batch Worker Script
echo "[3/5] Deploying Python Batch Processor script..."
cat << 'EOF' > "${SCRIPTS_DIR}/km_lexicon_mcp_batch.py"
import json
import logging
import urllib.request
import urllib.error
import time

HAPROXY_ENDPOINT = "http://127.0.0.1:11435/api/generate"
TYPESENSE_ENDPOINT = "http://127.0.0.1:8108/collections/km_lexicon_entries/documents"
TYPESENSE_API_KEY = "xyz"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def query_local_mcp_pool(raw_payload: dict) -> dict:
    prompt = f"[RULE SET Active] Parse and enrich for km_lexicon Typesense index: {json.dumps(raw_payload, ensure_ascii=False)}"
    payload = {
        "model": "qwen2.5-coder:14b",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    req = urllib.request.Request(
        HAPROXY_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return json.loads(res_data.get("response", "{}"))
    except Exception as e:
        logging.error(f"Local MCP pool error: {e}")
        return {}

def main_loop():
    logging.info("Starting km_lexicon processing loop connected to HAProxy (127.0.0.1:11435)")
    while True:
        # Worker execution pulse
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
EOF

chmod +x "${SCRIPTS_DIR}/km_lexicon_mcp_batch.py"

# 4. Generate Systemd User Service Configuration
echo "[4/5] Creating Systemd User Service..."
cat << EOF > "${SYSTEMD_USER_DIR}/${SERVICE_NAME}.service"
[Unit]
Description=km_lexicon Batch Processing Pipeline via Local HAProxy MCP
After=network.target

[Service]
Type=simple
WorkingDirectory=${BASE_DIR}
ExecStart=/usr/bin/env python3 ${SCRIPTS_DIR}/km_lexicon_mcp_batch.py
Restart=always
RestartSec=5
StandardOutput=append:${LOGS_DIR}/batch_process.log
StandardError=append:${LOGS_DIR}/batch_process_error.log

[Install]
WantedBy=default.target
EOF

# 5. Enable and Reload Systemd Service
echo "[5/5] Reloading Systemd and enabling service..."
systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"

echo "======================================================================"
echo "Deployment Complete!"
echo "Directories created under: ${BASE_DIR}"
echo ""
echo "To start the background worker service, run:"
echo "  systemctl --user start ${SERVICE_NAME}"
echo ""
echo "To check background worker logs, run:"
echo "  tail -f ${LOGS_DIR}/batch_process.log"
echo "======================================================================"