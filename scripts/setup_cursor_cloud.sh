#!/usr/bin/env bash
# Setup Cursor Cloud (origin.cursor.com) remote for pne_scheduler.
# Run from WSL: bash scripts/setup_cursor_cloud.sh

set -euo pipefail

REPO_NAME="pne_scheduler"
REMOTE_NAME="cursor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ORIGIN_BIN="${ORIGIN_BIN:-$HOME/.local/bin/origin}"
if ! command -v origin >/dev/null 2>&1; then
  if [[ -x "${ORIGIN_BIN}" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
  else
    echo "==> Installing origin CLI..."
    curl -fsSL https://downloads.cursor.com/origin/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
fi

echo "==> origin version: $(origin --version 2>/dev/null || echo unknown)"

echo "==> Checking origin auth..."
if ! origin auth status 2>/dev/null | grep -qi "logged in\|authenticated\|session"; then
  echo ""
  echo "Origin CLI login required. A browser window will open."
  echo "Complete login, then this script will continue."
  echo ""
  origin auth login
fi

cd "${REPO_ROOT}"
echo "==> Working in: ${REPO_ROOT}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: ${REPO_ROOT} is not a git repository." >&2
  exit 1
fi

BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo master)"
echo "==> Current branch: ${BRANCH}"

if git remote get-url "${REMOTE_NAME}" >/dev/null 2>&1; then
  CURSOR_URL="$(git remote get-url "${REMOTE_NAME}")"
  echo "==> Remote '${REMOTE_NAME}' already exists: ${CURSOR_URL}"
else
  echo "==> Creating Cursor Cloud repo '${REPO_NAME}'..."
  CREATE_OUT="$(origin repo create "${REPO_NAME}" 2>&1)" || {
    if echo "${CREATE_OUT}" | grep -qi "already exists\|taken"; then
      echo "==> Repo may already exist; trying to resolve clone URL..."
      CREATE_OUT="$(origin repo list 2>/dev/null || true)"
    else
      echo "${CREATE_OUT}" >&2
      exit 1
    fi
  }
  echo "${CREATE_OUT}"

  # Parse clone URL from create output (https://origin.cursor.com/...)
  CURSOR_URL="$(echo "${CREATE_OUT}" | grep -Eo 'https://origin\.cursor\.com[^ ]+' | head -1 || true)"
  if [[ -z "${CURSOR_URL}" ]]; then
    # Fallback: construct from namespace in repo list
    CURSOR_URL="$(origin repo list 2>/dev/null | grep -F "${REPO_NAME}" | grep -Eo 'https://origin\.cursor\.com[^ ]+' | head -1 || true)"
  fi
  if [[ -z "${CURSOR_URL}" ]]; then
    echo "ERROR: Could not determine Cursor clone URL. Run 'origin repo list' manually." >&2
    exit 1
  fi
  git remote add "${REMOTE_NAME}" "${CURSOR_URL}"
  echo "==> Added remote '${REMOTE_NAME}': ${CURSOR_URL}"
fi

echo "==> Pushing ${BRANCH} to ${REMOTE_NAME}..."
git push -u "${REMOTE_NAME}" "${BRANCH}"

CODEBASE_URL="$(git remote get-url "${REMOTE_NAME}" | sed -E 's|https://origin\.cursor\.com/||; s|\.git$||')"
echo ""
echo "Done."
echo "  Remote : ${REMOTE_NAME} -> $(git remote get-url "${REMOTE_NAME}")"
echo "  Page   : https://cursor.com/codebase/${CODEBASE_URL}"
echo "  GitHub : origin -> $(git remote get-url origin 2>/dev/null || echo n/a)"
