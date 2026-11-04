#!/usr/bin/env bash
# PDFTrans Pro installer (macOS / Linux / WSL)
#
# Usage 1 (recommended, one-liner remote install):
#   curl -fsSL https://raw.githubusercontent.com/palelunar/pdftrans-pro/main/install.sh | bash
#
# Usage 2 (local script, per-tool selection):
#   ./install.sh                        # install into every detected tool
#   ./install.sh codex                  # Codex only
#   ./install.sh claude                 # Claude Code only
#   ./install.sh opencode               # opencode only
#   ./install.sh dsh /path/to/deepseek-harness
set -euo pipefail

say()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

# ---- Locate sources: local script uses the repo copy; remote (curl|bash) mode downloads a GitHub archive ----
SRC1=""; SRC2=""; TMP_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SRC1="$REPO_DIR/claude-code/pdftrans-pro"
    SRC2="$REPO_DIR/deepseek-harness/pdftrans-pro"
else
    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT
    say "remote mode: downloading skill repo..."
    curl -fsSL https://github.com/palelunar/pdftrans-pro/archive/refs/heads/main.tar.gz -o "$TMP_DIR/repo.tar.gz" \
        || { warn "Download failed. Check your network/proxy and retry, or use local script mode."; exit 1; }
    tar -xzf "$TMP_DIR/repo.tar.gz" -C "$TMP_DIR" \
        || { warn "Could not unpack the downloaded archive. Retry, or use local script mode."; exit 1; }
    REPO_DIR="$TMP_DIR/pdftrans-pro-main"
    SRC1="$REPO_DIR/claude-code/pdftrans-pro"
    SRC2="$REPO_DIR/deepseek-harness/pdftrans-pro"
fi

installed=0

install_into() { # $1=source dir $2=target parent dir $3=tool name
    local src="$1" dst_dir="$2" tool="$3"
    if [ ! -d "$src" ]; then warn "Source dir not found: $src (skipped)"; return; fi
    mkdir -p "$dst_dir"
    rm -rf "$dst_dir/pdftrans-pro"
    cp -r "$src" "$dst_dir/pdftrans-pro"
    say "$tool -> $dst_dir/pdftrans-pro (installed; takes effect after restarting the session)"
    installed=1
}

if [ "$#" -ge 1 ] && [ "$1" = "codex" ]; then
    install_into "$SRC1" "$HOME/.agents/skills" "Codex"
elif [ "$#" -ge 1 ] && [ "$1" = "claude" ]; then
    install_into "$SRC1" "$HOME/.claude/skills" "Claude Code"
elif [ "$#" -ge 1 ] && [ "$1" = "opencode" ]; then
    install_into "$SRC1" "$HOME/.config/opencode/skill" "opencode"
elif [ "$#" -ge 1 ] && [ "$1" = "dsh" ]; then
    [ "$#" -ge 2 ] || { echo "Usage: ./install.sh dsh <deepseek-harness-checkout-path>"; exit 1; }
    install_into "$SRC2" "${2%/}/.agents/skills" "DeepSeek Harness"
else
    { [ -d "$HOME/.codex" ] || [ -d "$HOME/.agents" ]; } && install_into "$SRC1" "$HOME/.agents/skills" "Codex"
    [ -d "$HOME/.claude" ] && install_into "$SRC1" "$HOME/.claude/skills" "Claude Code"
    [ -d "$HOME/.config/opencode" ] && install_into "$SRC1" "$HOME/.config/opencode/skill" "opencode"
    [ -n "${DSH_HOME:-}" ] && [ -d "$DSH_HOME" ] && install_into "$SRC2" "$DSH_HOME/.agents/skills" "DeepSeek Harness"
    [ "$installed" -eq 0 ] && warn "No supported tool directories detected. Local mode: ./install.sh codex | claude | opencode | dsh <path>"
fi

if [ "$installed" -eq 1 ]; then
    say "Done. Restart the tool's session, then say it in natural language (e.g. \"translate this PDF\") and pdftrans-pro will be picked up automatically."
fi
