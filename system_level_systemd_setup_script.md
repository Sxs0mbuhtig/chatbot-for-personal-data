#!/usr/bin/env bash

# ==============================================================================
# km_lexicon System-Level Systemd Deployment Script
# Target: Create /etc/systemd/system/km-lexicon-batch.service
# Checked with ShellCheck (Zero Warnings)
# ==============================================================================

set -euo pipefail

SERVICE_FILE="/etc/systemd/system/km-lexicon-batch.service"
WORK_DIR="/home/sam_workstation/km_lexicon"
CONF_DIR="${WORK_DIR}/my_Apps"
SCRIPTS_DIR="${WORK_DIR}/scripts"
LOGS_DIR="${WORK_DIR}/logs"
USER_NAME="sam_workstation"
PYTHON_EXEC="${WORK_DIR}/venv/bin/python"
SCRIPT_EXEC="${SCRIPTS_DIR}/km_lexicon_mcp_batch.py"

# Ensure script is executed with root privileges
if [ "${EUID}" -ne 0 ]; then
    echo "Error: This script must be run with sudo or as root." >&2
    exit 1
fi

echo "======================================================================"
echo "Creating System-Level Systemd Service for km_lexicon"
echo "======================================================================"

# 1. Create Directories & Fix Ownership
echo "[1/5] Creating directory structure..."
mkdir -p "${CONF_DIR}" "${SCRIPTS_DIR}" "${LOGS_DIR}"

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
cat << 'EOF' > "${SCRIPT_EXEC}"
import json
import logging
import time
import urllib.error
import urllib.request

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
        time.sleep(10)

if __name__ == "__main__":
    main_loop()
EOF

chmod +x "${SCRIPT_EXEC}"

# Set ownership of workspace to sam_workstation
chown -R "${USER_NAME}:${USER_NAME}" "${WORK_DIR}"

# 4. Create Systemd Service File
echo "[4/5] Writing systemd service file to ${SERVICE_FILE}..."
cat << EOF > "${SERVICE_FILE}"
[Unit]
Description=km_lexicon Batch Processing Pipeline via Local HAProxy MCP
After=network.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${WORK_DIR}
ExecStart=${PYTHON_EXEC} ${SCRIPT_EXEC}
Restart=always
RestartSec=5
StandardOutput=append:${LOGS_DIR}/batch_process.log
StandardError=append:${LOGS_DIR}/batch_process_error.log

[Install]
WantedBy=multi-user.target
EOF

# 5. Reload systemd daemon and enable service
echo "[5/5] Reloading systemd daemon and enabling service..."
systemctl daemon-reload
systemctl enable km-lexicon-batch.service
systemctl restart km-lexicon-batch.service

echo "======================================================================"
echo "System-level installation complete!"
echo "Service Status: $(systemctl is-active km-lexicon-batch.service)"
echo "Check status via: sudo systemctl status km-lexicon-batch.service"
echo "======================================================================"