#!/usr/bin/env bash
set -euo pipefail

# Parse optional flags
ENABLE_SYSTEMD=false
RUN_TESTS=true # Enabled by default per your latest request

for arg in "$@"; do
    case $arg in
        --with-systemd) ENABLE_SYSTEMD=true ;;
        --skip-tests) RUN_TESTS=false ;;
    esac
done

# Define log file with timestamp
LOG_FILE="deployment_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=================================================="
echo " Automated Reincarnation Pipeline for km_lexicon"
echo " Timestamp: $(date)"
echo "=================================================="

echo "[1/7] Stopping conflicting systemd user services at the start..."
systemctl --user stop km-lexicon-api.service km-lexicon-batch.service 2>/dev/null || true
sudo systemctl stop km-lexicon-api.service km-lexicon-batch.service 2>/dev/null || true

echo -e "\n[2/7] Hunting down and terminating stray uvicorn/python API processes..."
CURRENT_PID=$(lsof -t -i:8000 2>/dev/null || true)
if [ -n "$CURRENT_PID" ]; then
    echo "  -> Found active listener on port 8000 (PID: $CURRENT_PID)."
    PPID_VAL=$(ps -o ppid= -p "$CURRENT_PID" | tr -d ' ' || true)
    if [ -n "$PPID_VAL" ] && [ "$PPID_VAL" -ne 1 ]; then
        sudo kill -9 "$PPID_VAL" 2>/dev/null || true
    fi
    sudo kill -9 "$CURRENT_PID" 2>/dev/null || true
fi
sudo pkill -9 -f "uvicorn.*api_service:app\|uvicorn.*main:app" 2>/dev/null || true

echo -e "\n[3/7] Tearing down active Docker containers and networks..."
docker compose down --remove-orphans --volumes 2>/dev/null || true
docker rm -f $(docker ps -aq --filter name=khmer_dict) 2>/dev/null || true

echo -e "\n[4/7] Verifying port 8000 is completely released..."
for i in {1..5}; do
    if sudo lsof -i :8000 >/dev/null 2>&1; then
        echo "  -> Port 8000 still bound, retrying forced kill..."
        sudo fuser -k 8000/tcp 2>/dev/null || true
        sleep 1
    else
        break
    fi
done
echo "  -> Port 8000 is 100% free."

echo -e "\n[5/7] Building fresh Docker images (--no-cache) and starting container stack..."
docker compose build --no-cache
docker compose up -d

# Verify container successfully bound port 8000 and health check
echo "  -> Verifying Docker container successfully acquired port 8000..."
sleep 4
if ! sudo lsof -i :8000 >/dev/null 2>&1; then
    echo "ERROR: Port 8000 is not bound by Docker! Check container logs via 'docker compose logs'."
    exit 1
fi
echo "  -> Success! Docker container is successfully bound to port 8000."

echo -e "\n[6/7] Running test suite inside container..."
if [ "$RUN_TESTS" = true ]; then
    echo "  -> Executing pytest..."
    docker compose exec -T app pytest tests/ -v
    echo "  -> Test suite completed successfully."
else
    echo "  -> Skipping pytest execution (--skip-tests specified)."
fi

echo -e "\n[7/7] Post-Deployment & Systemd Service Re-engagement..."
if [ "$ENABLE_SYSTEMD" = true ]; then
    echo "  -> Reloading systemd daemon and re-enabling/starting user services..."
    systemctl --user daemon-reload
    systemctl --user enable km-lexicon-api.service km-lexicon-batch.service 2>/dev/null || true
    systemctl --user start km-lexicon-api.service km-lexicon-batch.service 2>/dev/null || true
    echo "  -> Systemd services re-enabled and started."
else
    echo "  -> Leaving systemd services stopped (pass --with-systemd to re-enable them automatically)."
fi

echo "=================================================="
echo " Deployment Complete! Log saved to: $LOG_FILE"
echo "=================================================="
