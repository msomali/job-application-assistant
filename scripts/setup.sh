#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "=== Job Application Assistant — Setup ==="
echo ""

# ---- 1. Check Python version ----
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
    info "Python $PYTHON_VERSION"
else
    fail "Python $PYTHON_VERSION — need 3.11+"
    exit 1
fi

# ---- 2. Check pdflatex ----
if command -v pdflatex &>/dev/null; then
    info "pdflatex found"
else
    warn "pdflatex not found — PDF generation will not work"
    echo "    Install MacTeX: https://www.tug.org/mactex/"
    echo "    Or: brew install --cask mactex-no-gui"
    read -rp "    Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy] ]] || exit 1
fi

# ---- 3. Virtual environment ----
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -d .venv ]]; then
        warn "Virtual environment exists at .venv/ but is not active"
        echo "    Activate it: source .venv/bin/activate"
        read -rp "    Continue installing into current Python? [y/N] " ans
        [[ "$ans" =~ ^[Yy] ]] || exit 1
    else
        echo ""
        read -rp "Create virtual environment in .venv? [Y/n] " ans
        if [[ ! "$ans" =~ ^[Nn] ]]; then
            python3 -m venv .venv
            source .venv/bin/activate
            info "Created and activated .venv"
        fi
    fi
else
    info "Virtual environment active: $VIRTUAL_ENV"
fi

# ---- 4. Install package ----
echo ""
echo "Installing package with dev dependencies..."
pip install -e ".[dev]" --quiet
info "Package installed"

# ---- 5. Playwright ----
echo "Installing Playwright Chromium..."
playwright install chromium 2>/dev/null
info "Playwright Chromium installed"

# ---- 6. Copy example files ----
echo ""
echo "--- Data Files ---"

copy_if_missing() {
    local src="$1" dest="$2" desc="$3"
    if [[ -f "$dest" ]]; then
        info "$desc already exists"
    else
        cp "$src" "$dest"
        warn "$desc created from example — edit with your data"
    fi
}

copy_if_missing .env.example .env ".env"
copy_if_missing data/config.example.yaml data/config.yaml "data/config.yaml"
copy_if_missing data/master_resume.example.json data/master_resume.json "data/master_resume.json"
copy_if_missing data/search_config.example.json data/search_config.json "data/search_config.json"
copy_if_missing data/screening_answers.example.json data/screening_answers.json "data/screening_answers.json"

# ---- 7. API keys ----
echo ""
echo "--- API Keys ---"
if grep -q "your-api-key-here\|your-bot-token\|your-numeric-user" .env 2>/dev/null; then
    warn ".env has placeholder values"
    echo ""

    read -rp "  Firecrawl API key (firecrawl.dev, Enter to skip): " fc_key
    if [[ -n "$fc_key" ]]; then
        sed -i '' "s|fc-your-api-key-here|$fc_key|" .env
    fi

    read -rp "  Anthropic API key (console.anthropic.com, Enter to skip): " ant_key
    if [[ -n "$ant_key" ]]; then
        sed -i '' "s|sk-ant-your-api-key-here|$ant_key|" .env
    fi

    read -rp "  Telegram Bot Token (@BotFather, Enter to skip): " tg_token
    if [[ -n "$tg_token" ]]; then
        sed -i '' "s|your-bot-token-from-botfather|$tg_token|" .env
    fi

    read -rp "  Telegram User ID (@userinfobot, Enter to skip): " tg_uid
    if [[ -n "$tg_uid" ]]; then
        sed -i '' "s|your-numeric-user-id|$tg_uid|" .env
    fi

    info "API keys updated in .env"
else
    info ".env already configured"
fi

# ---- 8. Pre-commit hooks ----
if command -v pre-commit &>/dev/null; then
    pre-commit install --quiet 2>/dev/null
    info "Pre-commit hooks installed"
fi

# ---- 9. Create output and logs directories ----
mkdir -p output logs
info "Output and logs directories ready"

# ---- Done ----
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit data/master_resume.json with your actual resume"
echo "  2. Edit data/search_config.json with your job search queries"
echo "  3. Edit data/screening_answers.json with your screening answers"
echo "  4. Add API keys to .env if you skipped them above"
echo ""
echo "Verify:  make verify"
echo "Run:     job discover --analyze-all"
echo "Bot:     make bot"
echo ""
