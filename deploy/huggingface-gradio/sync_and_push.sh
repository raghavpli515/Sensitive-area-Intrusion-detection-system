#!/usr/bin/env bash
# Assembles the minimal subset this Gradio Space actually needs — the
# framework-agnostic core/services/schemas modules (no FastAPI/api/main.py,
# none of that is used here), real model weights (not the DVC pointer), and
# this directory's demo.py/requirements.txt/README.md — into a throwaway
# directory, and pushes it as a single commit to the Space's git remote.
#
# Usage:
#   deploy/huggingface-gradio/sync_and_push.sh <space-git-url> ["commit message"]
#
# Requires the credential already cached (see repo root README's HF Space
# setup steps) and git-lfs installed. Force-pushes — the Space repo is a
# disposable deploy artifact, not something with history worth preserving.
set -euo pipefail

SPACE_URL="${1:?Usage: sync_and_push.sh <space-git-url> [\"commit message\"]}"
MESSAGE="${2:-Sync from main repo}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_PATH="$REPO_ROOT/models/yolov8_model.pt"

if [ ! -f "$MODEL_PATH" ]; then
  echo "ERROR: $MODEL_PATH not found." >&2
  echo "Run 'dvc pull' or place the weights there first." >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Assembling Space snapshot in $WORKDIR ..."
mkdir -p "$WORKDIR/app/core" "$WORKDIR/app/services" "$WORKDIR/app/schemas" "$WORKDIR/models"

SRC="$REPO_ROOT/backend/app"
cp "$SRC/__init__.py" "$WORKDIR/app/"
cp "$SRC/core/__init__.py" "$SRC/core/detector.py" "$SRC/core/tracker.py" \
   "$SRC/core/rules.py" "$SRC/core/registry.py" "$WORKDIR/app/core/"
cp "$SRC/services/__init__.py" "$SRC/services/pipeline.py" "$SRC/services/jobs.py" \
   "$WORKDIR/app/services/"
cp "$SRC/schemas/__init__.py" "$SRC/schemas/detection.py" "$WORKDIR/app/schemas/"

cp "$MODEL_PATH" "$WORKDIR/models/yolov8_model.pt"
cp "$REPO_ROOT/deploy/huggingface-gradio/demo.py" "$WORKDIR/"
cp "$REPO_ROOT/deploy/huggingface-gradio/requirements.txt" "$WORKDIR/"
cp "$REPO_ROOT/deploy/huggingface-gradio/README.md" "$WORKDIR/"

cd "$WORKDIR"
git init -q -b main
git lfs install --local >/dev/null
git lfs track "*.pt" >/dev/null
git add -A
git commit -q -m "$MESSAGE"
git remote add space "$SPACE_URL"

echo "Pushing to $SPACE_URL ..."
git push --force space main

echo "Done. The Space will rebuild automatically."
