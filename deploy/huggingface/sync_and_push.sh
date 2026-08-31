#!/usr/bin/env bash
# Assembles a minimal snapshot of what the Hugging Face Space actually needs
# (backend/frontend source, real model weights, the Space Dockerfile/README)
# into a throwaway directory, and pushes it as a single commit to the
# Space's own git remote.
#
# The Space is intentionally NOT a checkout of this whole repo: its
# README.md needs HF-specific frontmatter that would clash with the real
# project README (see deploy/huggingface/README.md vs the repo root one),
# and it needs real model bytes rather than a DVC pointer the Space can't
# resolve (no access to the personal Google Drive remote). Re-run this
# script any time you want the live demo to reflect a new push to main.
#
# Usage:
#   deploy/huggingface/sync_and_push.sh <space-git-url> ["commit message"]
#
# <space-git-url> looks like https://huggingface.co/spaces/<user>/<space>.
# Requires `huggingface-cli login` (or credentials already cached by git)
# and git-lfs installed. Force-pushes — the Space repo is a disposable
# deploy artifact, not something with history worth preserving.
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
mkdir -p "$WORKDIR/backend" "$WORKDIR/models"

cp -r "$REPO_ROOT/backend/app" "$WORKDIR/backend/app"
cp "$REPO_ROOT/backend/requirements.txt" "$WORKDIR/backend/"

mkdir -p "$WORKDIR/frontend"
cp -r "$REPO_ROOT/frontend/src" "$REPO_ROOT/frontend/public" "$WORKDIR/frontend/"
cp "$REPO_ROOT/frontend/package.json" "$REPO_ROOT/frontend/package-lock.json" \
   "$REPO_ROOT/frontend/index.html" "$REPO_ROOT/frontend/vite.config.ts" \
   "$REPO_ROOT/frontend/tsconfig.json" "$REPO_ROOT/frontend/tsconfig.app.json" \
   "$REPO_ROOT/frontend/tsconfig.node.json" \
   "$WORKDIR/frontend/"

cp "$MODEL_PATH" "$WORKDIR/models/yolov8_model.pt"
cp "$REPO_ROOT/deploy/huggingface/Dockerfile" "$WORKDIR/Dockerfile"
cp "$REPO_ROOT/deploy/huggingface/README.md" "$WORKDIR/README.md"

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
