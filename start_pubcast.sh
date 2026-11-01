#!/usr/bin/env bash
# PubCast AI v5.5 — Production Startup Script
# Rear View Foresight LLC — Feic Mo Chroí

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}"
echo "═══════════════════════════════════════════════════════════"
echo "  PubCast AI v5.5 — Production Startup"
echo "  Rear View Foresight LLC — Feic Mo Chroí™"
echo "═══════════════════════════════════════════════════════════"
echo -e "${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check Python version
echo -e "${BOLD}[1/5] Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.10"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    print_status "Python $python_version (>= $required_version required)"
else
    print_error "Python 3.10+ required, found $python_version"
    exit 1
fi

# Check dependencies
echo -e "\n${BOLD}[2/5] Checking dependencies...${NC}"

missing_deps=0
while IFS= read -r dep; do
    if python3 -c "import $dep" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $dep"
    else
        echo -e "  ${RED}✗${NC} $dep ${YELLOW}(missing)${NC}"
        missing_deps=$((missing_deps + 1))
    fi
done << EOF
fastapi
uvicorn
pydantic
aiofiles
EOF

if [ $missing_deps -gt 0 ]; then
    print_warning "$missing_deps dependencies missing"
    echo -e "\nInstall with: ${BOLD}pip install fastapi uvicorn pydantic aiofiles${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_status "All dependencies installed"
fi

# Verify data directories
echo -e "\n${BOLD}[3/5] Verifying data directories...${NC}"

# This list must stay aligned with _check_data_dirs() in modules/doctor.py.
# It previously did not: the doctor treats data/, recordings, emergency_saves,
# exports, byok and credentials as a REQUIRED launch-gate check, while this
# script created a different set and never created credentials, emergency_saves,
# exports or byok at all. A fresh install therefore failed its own launch gate,
# and running this script did not repair it.
dirs_to_check=(
    "data"
    "data/recordings"
    "data/emergency_saves"
    "data/exports"
    "data/byok"
    "data/credentials"
    "data/timelines"
    "data/hotspots"
    "data/environments"
    "data/logs"
    "static"
)

for dir in "${dirs_to_check[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ${GREEN}✓${NC} $dir"
    else
        echo -e "  ${YELLOW}⚠${NC} $dir ${YELLOW}(creating)${NC}"
        mkdir -p "$dir"
    fi
done

# Count timeline and hotspot files
timeline_count=$(ls data/timelines/*.json 2>/dev/null | wc -l)
hotspot_count=$(ls data/hotspots/*.json 2>/dev/null | wc -l)
print_status "$timeline_count timeline files, $hotspot_count hotspot files"

# Run integration tests
echo -e "\n${BOLD}[4/5] Running integration tests...${NC}"

if [ -f "test_v55_integration.py" ]; then
    if python3 test_v55_integration.py >/dev/null 2>&1; then
        print_status "All integration tests passed"
    else
        print_warning "Some integration tests failed"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    print_warning "Integration tests not found (skipping)"
fi

# Check for required files
echo -e "\n${BOLD}[5/5] Checking required files...${NC}"

required_files=(
    "main.py"
    "modules/timeline_routes.py"
    "modules/structured_log_routes.py"
    "modules/recording_pipeline_routes.py"
    "modules/governance_waiting_room.py"
    "modules/hotspot_system.py"
)

all_present=true
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file ${RED}(missing!)${NC}"
        all_present=false
    fi
done

if [ "$all_present" = false ]; then
    print_error "Required files missing - cannot start"
    exit 1
fi

# Display startup info
echo -e "\n${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Startup checks complete — opening Foresight${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${BOLD}Server will be available at:${NC}"
echo -e "  ${BLUE}http://localhost:8000${NC}"
echo -e "\n${BOLD}Key endpoints:${NC}"
echo -e "  ${BLUE}http://localhost:8000/foresight (main UI)
  ${BLUE}http://localhost:8000/health${NC}           - System health check"
echo -e "  ${BLUE}http://localhost:8000/airlock${NC}          - Waiting room UI"
echo -e "  ${BLUE}http://localhost:8000/static/stage.html${NC} - Main stage"
echo -e "\n${BOLD}API endpoints:${NC}"
echo -e "  ${BLUE}/api/timeline/*${NC}      - Timeline automation"
echo -e "  ${BLUE}/api/logs/*${NC}          - Structured logging"
echo -e "  ${BLUE}/api/hotspots/*${NC}      - Interactive hotspots"
echo -e "  ${BLUE}/api/recording/*${NC}     - Recording pipeline"
echo -e "\n${BOLD}Press Ctrl+C to stop${NC}\n"

# Add small delay for dramatic effect
sleep 1

# Start server
echo -e "${BOLD}Starting server...${NC}\n"
exec python3 run_reach.py "$@"
