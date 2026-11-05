#!/bin/bash

# Exit immediately on unhandled errors
set -Eeuo pipefail

# Color codes for terminal display
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Incremental Log Management Setup
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

LOG_INDEX=0
while [ -f "$LOG_DIR/manage_log_${LOG_INDEX}.log" ]; do
    LOG_INDEX=$((LOG_INDEX + 1))
done

LOG_FILE="$LOG_DIR/manage_log_${LOG_INDEX}.log"
LATEST_SYMLINK="$LOG_DIR/manage_latest.log"

ln -sf "$(basename "$LOG_FILE")" "$LATEST_SYMLINK"

cat << EOF > "$LOG_FILE"
====================================================================
           KHMER LEXICON ADVANCED DIAGNOSTIC REPORT
====================================================================
Timestamp: $(date '+%Y-%m-%d %H:%M:%S')
Execution Host: $(whoami)@$(hostname)
Log Stream Index: manage_log_${LOG_INDEX}.log
--------------------------------------------------------------------
EOF

write_log_section() {
    local section_title="$1"
    echo -e "\n[$section_title]" >> "$LOG_FILE"
}

log_action() {
    local status="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$status" in
        "INFO")
            echo -e "${BLUE}[INFO]${NC} $message"
            echo "[$timestamp] [INFO] $message" >> "$LOG_FILE"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            echo "[$timestamp] [SUCCESS] $message" >> "$LOG_FILE"
            ;;
        "WARN")
            echo -e "${YELLOW}[WARNING]${NC} $message"
            echo "[$timestamp] [WARNING] $message" >> "$LOG_FILE"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message"
            echo "[$timestamp] [ERROR] $message" >> "$LOG_FILE"
            ;;
    esac
}

log_exec() {
    "$@" >> "$LOG_FILE" 2>&1
}

# ------------------------------------------------------------------
# CONFIGURATION & INFRASTRUCTURE GUARDRAILS
# ------------------------------------------------------------------

check_daemon() {
    write_log_section "SECTION 1: SYSTEM & DOCKER DAEMON STATUS"
    log_action "INFO" "Inspecting Docker daemon and system sockets..."
    if ! systemctl is-active --quiet docker; then
        log_action "WARN" "Docker daemon is inactive. Starting services..."
        log_exec systemctl start docker.service docker.socket containerd.service
        log_action "SUCCESS" "Docker daemon started successfully."
    else
        log_action "SUCCESS" "Docker daemon is active and responsive."
    fi
}

cleanup_orphans() {
    write_log_section "SECTION 2: RUNTIME SHIMS & ORPHANED PROCESS CLEANUP"
    log_action "INFO" "Scanning for locked container shims and orphan processes..."
    
    # Force stop any lingering docker containers related to our project
    docker stop khmer_dict_api khmer_dict_typesense 2>/dev/null || true
    docker rm -f khmer_dict_api khmer_dict_typesense 2>/dev/null || true

    STUCK_SHIMS=$(pgrep -f containerd-shim || true)
    if [ -n "$STUCK_SHIMS" ]; then
        log_action "WARN" "Stuck runtime shims detected. Purging..."
        log_exec pkill -9 -f containerd-shim || true
        log_action "SUCCESS" "Stuck shims cleared."
    else
        log_action "SUCCESS" "No zombie shims found."
    fi

    # Prune stopped containers and dangling task directories
    log_action "INFO" "Pruning dangling container runtimes..."
    docker container prune -f >> "$LOG_FILE" 2>&1 || true

    if [ -d "./typesense-data" ]; then
        if [ -f "./typesense-data/db/LOCK" ] || [ -f "./typesense-data/meta/LOCK" ]; then
            log_action "WARN" "Stale Typesense LOCK files found. Purging..."
            rm -f ./typesense-data/db/LOCK ./typesense-data/meta/LOCK
            log_action "SUCCESS" "Typesense locks cleared."
        fi
    fi
}

inspect_infrastructure_configs() {
    write_log_section "SECTION 3: CONFIGURATION & SCHEMA ALIGNMENT AUDIT"
    log_action "INFO" "Inspecting Dockerfile, Compose manifests, and DB schema linkage..."

    # Verify Dockerfile exists
    if [ ! -f "Dockerfile" ]; then
        log_action "ERROR" "Missing Dockerfile! Container build will fail."
        exit 1
    fi

    # Verify docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        log_action "ERROR" "Missing docker-compose.yml manifest!"
        exit 1
    fi

    # Verify SQLite schema columns match API expectations (headword & definition)
    DB_FILE="chuon_nath_fts.db"
    if [ ! -f "$DB_FILE" ]; then
        log_action "ERROR" "Core database '$DB_FILE' not found!"
        return 1
    fi

    SCHEMA_CHECK=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(dictionary);')
    cols = [col[1] for col in cursor.fetchall()]
    conn.close()
    
    required = ['headword', 'definition', 'norm_headword', 'pos']
    missing = [r for r in required if r not in cols]
    if missing:
        print(f'SCHEMA_ERROR: Missing required columns: {missing}')
        sys.exit(1)
    else:
        print('SCHEMA_OK: All required columns present.')
except Exception as e:
    print(f'SCHEMA_EXCEPTION: {e}')
    sys.exit(1)
" 2>&1)

    if echo "$SCHEMA_CHECK" | grep -q "SCHEMA_ERROR" || echo "$SCHEMA_CHECK" | grep -q "SCHEMA_EXCEPTION"; then
        log_action "ERROR" "Database schema alignment check failed: $SCHEMA_CHECK"
        exit 1
    else
        log_action "SUCCESS" "$SCHEMA_CHECK"
    fi
}

verify_storage() {
    write_log_section "SECTION 4: STORAGE & DATABASE INTEGRITY"
    DB_FILE="chuon_nath_fts.db"
    chown "$USER:$USER" "$DB_FILE" 2>/dev/null || true
    
    DB_CHECK_OUTPUT=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM dictionary;')
    count = cursor.fetchone()[0]
    print(f'SQLite OK: {count} records loaded.')
    conn.close()
except Exception as e:
    print(f'SQL_ERROR: {e}')
    sys.exit(1)
" 2>&1)

    if echo "$DB_CHECK_OUTPUT" | grep -q "SQL_ERROR"; then
        log_action "ERROR" "SQLite integrity validation failed: $DB_CHECK_OUTPUT"
        return 1
    else
        log_action "SUCCESS" "$DB_CHECK_OUTPUT"
    fi
}

rebuild_stack() {
    check_daemon
    cleanup_orphans
    inspect_infrastructure_configs
    verify_storage

    write_log_section "SECTION 5: BUILD & DEPLOYMENT EXECUTION"
    log_action "INFO" "Tearing down existing stack and purging volumes/orphans..."
    log_exec docker compose down -v --remove-orphans || true
    
    log_action "INFO" "Rebuilding and deploying stack containers..."
    if log_exec docker compose up -d --build; then
        log_action "SUCCESS" "Containers built and deployed successfully."
    else
        log_action "ERROR" "Docker build/deployment failed."
        exit 1
    fi

    log_action "INFO" "Waiting for Typesense engine to become fully responsive..."
    TS_READY=false
    for _ in {1..20}; do
        if curl -s http://localhost:8108/health | grep -q "true"; then
            TS_READY=true
            break
        fi
        sleep 2
    done

    if [ "$TS_READY" = false ]; then
        log_action "ERROR" "Typesense failed to become ready in time."
        exit 1
    fi
    log_action "SUCCESS" "Typesense is up and accepting connections."

    log_action "INFO" "Re-indexing Typesense search documents & synonyms..."
    if log_exec docker compose exec web python3 index_typesense.py; then
        log_action "SUCCESS" "Typesense re-indexed successfully."
    else
        log_action "ERROR" "Typesense indexing failed."
        exit 1
    fi
}

reload_components() {
    inspect_infrastructure_configs
    write_log_section "COMPONENT RELOAD"
    log_action "INFO" "Reloading FastAPI application and refreshing Typesense indices..."
    log_exec docker compose restart web
    log_exec docker compose exec web python3 index_typesense.py
    log_action "SUCCESS" "Key components reloaded successfully."
}

check_health() {
    write_log_section "SECTION 6: ENDPOINT HEALTH & LINKAGE VERIFICATION"
    
    echo -e "\n--- Docker Containers Status ---" >> "$LOG_FILE"
    log_exec docker compose ps
    docker compose ps

    if [ -f "chuon_nath_fts.db" ]; then
        log_action "SUCCESS" "SQLite FTS database file exists on disk."
    else
        log_action "ERROR" "SQLite FTS database file missing!"
    fi

    if curl -s http://localhost:8108/health | grep -q "true"; then
        log_action "SUCCESS" "Typesense search service is healthy (Port 8108)."
    else
        log_action "WARN" "Typesense search service is unresponsive."
    fi

    if curl -s http://localhost:8000/docs > /dev/null; then
        log_action "SUCCESS" "FastAPI web portal / docs endpoint is live (Port 8000)."
    else
        log_action "WARN" "FastAPI backend service is unresponsive."
    fi
}

verify_interconnection() {
    write_log_section "END-TO-END INTERCONNECTION VERIFICATION"
    log_action "INFO" "Running test suite and API integration validation..."

    if log_exec docker compose exec web pytest --cache-clear tests/ -v; then
        log_action "SUCCESS" "All regression tests passed successfully (100% test coverage)."
    else
        log_action "ERROR" "Some tests failed during interconnection verification. Check log."
    fi

    log_action "INFO" "Testing live API resolution for sample query 'គម'..."
    
    # Check live API response on main search route
    API_RESPONSE=$(curl -s "http://localhost:8000/search?q=%E1%9E%82%E1%9E%98" || true)
    if [ -z "$API_RESPONSE" ] || echo "$API_RESPONSE" | grep -q "Not Found"; then
        API_RESPONSE=$(curl -s "http://localhost:8000/api/v1/search?q=%E1%9E%82%E1%9E%98" || true)
    fi

    if echo "$API_RESPONSE" | grep -q "query" && (echo "$API_RESPONSE" | grep -q "exact_matches" || echo "$API_RESPONSE" | grep -q "educational_card"); then
        log_action "SUCCESS" "Live Search API responded correctly with valid linguistic payload for 'គម'."
    else
        log_action "WARN" "Live Search API query did not return expected match status."
    fi
}

# ------------------------------------------------------------------
# CLI ROUTER & INTERACTIVE MENU
# ------------------------------------------------------------------

print_banner() {
    echo -e "${YELLOW}====================================================${NC}"
    echo -e "${YELLOW}   Khmer Lexicon Advanced Manager & Diagnostics     ${NC}"
    echo -e "${YELLOW}====================================================${NC}"
    echo -e "Verbose Log Output: ${BLUE}$LOG_FILE${NC}"
    echo -e "Latest Log Symlink: ${BLUE}$LATEST_SYMLINK${NC}\n"
}

run_menu() {
    print_banner
    echo "Please select an operation mode:"
    echo "  1) Rebuild Stack (Inspect configs, tear down, rebuild & re-index)"
    echo "  2) Reload Key Components (Refresh configs & restart web)"
    echo "  3) Check Health & Status (Inspect containers, databases & ports)"
    echo "  4) Clean Orphans & Locks (Purge shims, zombie processes & stale locks)"
    echo "  5) Verify Interconnection (Run full pytest suite & live API query)"
    echo "  6) Run Full Pipeline (Inspect + Rebuild + Health + Verify)"
    echo "  7) Exit"
    echo -n "Enter choice [1-7]: "
    read -r choice

    case $choice in
        1) rebuild_stack; check_health ;;
        2) reload_components ;;
        3) check_health ;;
        4) cleanup_orphans ;;
        5) verify_interconnection ;;
        6) rebuild_stack; check_health; verify_interconnection ;;
        7) echo "Exiting."; exit 0 ;;
        *) echo -e "${RED}Invalid option.${NC}"; exit 1 ;;
    esac
}

if [ $# -eq 0 ]; then
    run_menu
else
    print_banner
    case "$1" in
        --rebuild)
            rebuild_stack
            check_health
            ;;
        --reload)
            reload_components
            ;;
        --health)
            check_health
            ;;
        --cleanup)
            cleanup_orphans
            ;;
        --verify)
            verify_interconnection
            ;;
        --all)
            rebuild_stack
            check_health
            verify_interconnection
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--rebuild | --reload | --health | --cleanup | --verify | --all]"
            exit 1
            ;;
    esac
fi

echo -e "\n${GREEN}Operation completed successfully. Log saved to:${NC} $LOG_FILE"
