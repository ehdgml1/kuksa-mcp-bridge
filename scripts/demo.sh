#!/usr/bin/env bash
# demo.sh — kuksa-mcp-bridge Demo Launcher
#
# Usage: ./scripts/demo.sh [mode1|mode2|mode3]
#
#   mode1  (default) Engine Warning — DTC Diagnosis Demo
#   mode2            DBC Vehicle Swap Demo (Hyundai → Tesla)
#   mode3            Normal Driving — UI Showcase

set -euo pipefail

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

# ---------------------------------------------------------------------------
# Utility: print_header
# ---------------------------------------------------------------------------
print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  kuksa-mcp-bridge Demo Launcher${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Utility: print_step STEP_NUM TOTAL DESCRIPTION
# ---------------------------------------------------------------------------
print_step() {
    local step_num="$1"
    local total="$2"
    local description="$3"
    echo -e "${GREEN}Step ${step_num}/${total}:${NC} ${description}"
}

# ---------------------------------------------------------------------------
# Utility: update_env_var KEY VALUE
# Updates or appends KEY=VALUE in .env, handles macOS vs Linux sed -i
# ---------------------------------------------------------------------------
update_env_var() {
    local key="$1"
    local value="$2"

    # Create .env from .env.example if it does not exist
    if [[ ! -f "${ENV_FILE}" ]]; then
        if [[ -f "${PROJECT_ROOT}/.env.example" ]]; then
            cp "${PROJECT_ROOT}/.env.example" "${ENV_FILE}"
        else
            touch "${ENV_FILE}"
        fi
    fi

    if grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
        # Key exists — update in-place (macOS vs Linux)
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
        fi
    else
        # Key absent — append
        echo "${key}=${value}" >> "${ENV_FILE}"
    fi
}

# ---------------------------------------------------------------------------
# Utility: wait_for_healthy TIMEOUT_SECONDS
# Polls `docker compose ps` until all services are healthy/running.
# ---------------------------------------------------------------------------
wait_for_healthy() {
    local timeout="${1:-60}"
    local elapsed=0
    local interval=3

    echo -e "${YELLOW}Waiting for services to become healthy (timeout: ${timeout}s)...${NC}"

    while [[ "${elapsed}" -lt "${timeout}" ]]; do
        # Count containers that are NOT yet in a healthy/running state.
        # `docker compose ps` columns: NAME SERVICE IMAGE COMMAND SERVICE CREATED STATUS PORTS
        # STATUS examples: "Up 5 seconds (healthy)", "Up 10 seconds", "Exit 1"
        local not_ready
        not_ready=$(
            docker compose ps --format "{{.Status}}" 2>/dev/null \
            | grep -vE "(healthy|running|Up)" \
            | grep -c "." || true
        )

        local total
        total=$(docker compose ps --format "{{.Status}}" 2>/dev/null | grep -c "." || true)

        if [[ "${total}" -gt 0 && "${not_ready}" -eq 0 ]]; then
            echo -e "${GREEN}All ${total} service(s) are ready.${NC}"
            return 0
        fi

        sleep "${interval}"
        elapsed=$(( elapsed + interval ))
        echo -e "  ${CYAN}...still waiting (${elapsed}s elapsed)${NC}"
    done

    echo -e "${RED}Timeout after ${timeout}s. Some services may not be healthy.${NC}"
    docker compose ps
    return 1
}

# ---------------------------------------------------------------------------
# Mode 1: Engine Warning — DTC Diagnosis Demo
# ---------------------------------------------------------------------------
run_mode1() {
    echo -e "${BOLD}[Mode 1] Engine Warning — DTC Diagnosis Demo${NC}"
    echo ""

    print_step 1 4 "Configuring simulator mode..."
    update_env_var "SIM_MODE" "engine_warning"

    print_step 2 4 "Starting services..."
    (cd "${PROJECT_ROOT}" && docker compose up -d)

    print_step 3 4 "Waiting for services to be healthy..."
    (cd "${PROJECT_ROOT}" && wait_for_healthy 60)

    print_step 4 4 "All services ready!"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:5180"
    echo -e "  ${CYAN}Agent API:${NC}  http://localhost:8000"
    echo ""
    echo -e "  ${YELLOW}Try asking:${NC} \"엔진 경고등이 켜졌고 이상한 소리가 나요\""
    echo -e "  ${YELLOW}Or:${NC}         \"차량 DTC 진단해줘\""
}

# ---------------------------------------------------------------------------
# Mode 2: DBC Vehicle Swap (Hyundai → Tesla)
# ---------------------------------------------------------------------------
run_mode2() {
    echo -e "${BOLD}[Mode 2] DBC Vehicle Swap Demo (Hyundai → Tesla)${NC}"
    echo ""

    print_step 1 4 "Bringing down current services..."
    (cd "${PROJECT_ROOT}" && docker compose down)

    print_step 2 4 "Switching vehicle profile to Tesla Model 3..."
    update_env_var "VEHICLE_PROFILE" "tesla_model3"

    print_step 3 4 "Starting services with DBC feeder profile..."
    (cd "${PROJECT_ROOT}" && docker compose --profile dbc-feeder up -d)

    print_step 4 4 "Waiting for services to be healthy..."
    (cd "${PROJECT_ROOT}" && wait_for_healthy 60)

    echo ""
    echo -e "  ${GREEN}All services ready!${NC}"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:5180"
    echo -e "  ${CYAN}Agent API:${NC}  http://localhost:8000"
    echo ""
    echo -e "  ${YELLOW}Vehicle profile:${NC}  Tesla Model 3 (via DBC feeder)"
    echo -e "  ${YELLOW}Try asking:${NC}       \"배터리 충전 상태 알려줘\""
    echo -e "  ${YELLOW}Switch back:${NC}      ./scripts/demo.sh mode1"
}

# ---------------------------------------------------------------------------
# Mode 3: Normal Driving — UI Showcase
# ---------------------------------------------------------------------------
run_mode3() {
    echo -e "${BOLD}[Mode 3] Normal Driving — UI Showcase${NC}"
    echo ""

    print_step 1 4 "Configuring simulator mode..."
    update_env_var "SIM_MODE" "normal_driving"

    print_step 2 4 "Starting services..."
    (cd "${PROJECT_ROOT}" && docker compose up -d)

    print_step 3 4 "Waiting for services to be healthy..."
    (cd "${PROJECT_ROOT}" && wait_for_healthy 60)

    print_step 4 4 "All services ready!"
    echo ""
    echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:5180"
    echo -e "  ${CYAN}Agent API:${NC}  http://localhost:8000"
    echo ""
    echo -e "  ${YELLOW}Try asking:${NC} \"차량 상태 점검해줘\""
    echo -e "  ${YELLOW}Or:${NC}         \"현재 속도와 RPM 알려줘\""
}

# ---------------------------------------------------------------------------
# Usage / help
# ---------------------------------------------------------------------------
usage() {
    echo "Usage: $(basename "$0") [mode1|mode2|mode3]"
    echo ""
    echo "  mode1  (default)  Engine Warning — DTC Diagnosis Demo"
    echo "  mode2             DBC Vehicle Swap Demo (Hyundai → Tesla)"
    echo "  mode3             Normal Driving — UI Showcase"
    echo ""
    exit 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local mode="${1:-mode1}"

    print_header

    case "${mode}" in
        mode1)
            run_mode1
            ;;
        mode2)
            run_mode2
            ;;
        mode3)
            run_mode3
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown mode: ${mode}${NC}"
            echo ""
            usage
            ;;
    esac

    echo ""
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════${NC}"
    echo ""
}

main "$@"
