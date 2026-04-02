#!/usr/bin/env python3
"""Verify that the project setup is complete."""

import shutil
import sys
from pathlib import Path

GREEN = "\033[32m"
RED = "\033[31m"
NC = "\033[0m"

ok = True


def check(label: str, passed: bool, hint: str = "") -> None:
    global ok
    mark = f"{GREEN}✓{NC}" if passed else f"{RED}✗ {hint}{NC}"
    print(f"  {label:<28} {mark}")
    ok = ok and passed


print("Checking setup...\n")

# Python version
py = f"{sys.version_info.major}.{sys.version_info.minor}"
check(f"Python {py}", sys.version_info >= (3, 11), "need 3.11+")

# pdflatex
check("pdflatex", bool(shutil.which("pdflatex")), "install MacTeX")

print()

# Config files
for name, path in [
    (".env", ".env"),
    ("config.yaml", "data/config.yaml"),
    ("master_resume.json", "data/master_resume.json"),
    ("search_config.json", "data/search_config.json"),
    ("screening_answers.json", "data/screening_answers.json"),
]:
    check(name, Path(path).exists(), "copy from example")

print()

# Python packages
for pkg in ["anthropic", "click", "pydantic", "playwright", "firecrawl"]:
    try:
        __import__(pkg)
        found = True
    except ImportError:
        found = False
    check(pkg, found, "run: make dev")

print()
print(f"{GREEN}Setup complete ✓{NC}" if ok else f"{RED}Setup incomplete — fix items marked ✗{NC}")
sys.exit(0 if ok else 1)
