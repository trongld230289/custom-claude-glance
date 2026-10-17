#!/usr/bin/env bash
# claude-glance installer for macOS / Linux / Git Bash
#
#   One-liner (global):
#     curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/claude-glance/main/install.sh | bash
#   One-liner with options:
#     curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/claude-glance/main/install.sh | bash -s -- --all-accounts
#   From a clone:
#     ./install.sh [--project [PATH]] [--all-accounts] [--uninstall]
set -euo pipefail
REPO="YOUR_GITHUB_USERNAME/claude-glance"
BRANCH="main"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "Python 3 was not found. Install it first (macOS: brew install python3)." >&2
  exit 1
fi

DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [ -n "$DIR" ] && [ -f "$DIR/glance.py" ]; then
  SRC="$DIR"
else
  SRC="$(mktemp -d)"
  for f in glance.py install.py; do
    curl -fsSL "https://raw.githubusercontent.com/$REPO/$BRANCH/$f" -o "$SRC/$f"
  done
fi

exec "$PY" "$SRC/install.py" "$@"
