#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="${1:-}"
if [[ -z "${SKILL_NAME}" ]]; then
  echo "Usage: $0 <skill-name>" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${REPO_ROOT}/skills/${SKILL_NAME}"
if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Skill not found: ${SRC_DIR}" >&2
  exit 2
fi

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
DEST_DIR="${CODEX_HOME}/skills/${SKILL_NAME}"

mkdir -p "$(dirname "${DEST_DIR}")"

# Copy over (no destructive rm); overwrite files but preserve other skills.
cp -a "${SRC_DIR}/." "${DEST_DIR}/"

echo "Installed skill '${SKILL_NAME}' to: ${DEST_DIR}"

