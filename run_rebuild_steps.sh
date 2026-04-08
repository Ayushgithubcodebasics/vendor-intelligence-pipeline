#!/usr/bin/env bash
# run_rebuild_steps.sh — cross-platform equivalent of run_rebuild_steps.ps1
# Works on macOS and Linux. For Windows, use run_rebuild_steps.ps1 instead.
#
# Usage:
#   bash run_rebuild_steps.sh            # full rebuild on raw data (data/raw/)
#   bash run_rebuild_steps.sh --sample   # quick rebuild using data/sample/ (CI / inspection)
#   bash run_rebuild_steps.sh --test     # run test suite only (no rebuild)

set -euo pipefail

case "${1:-}" in
  --test)
    echo "[run] Skipping rebuild — running test suite only..."
    python -m pytest tests/ -v
    exit 0
    ;;
  --sample)
    echo "[run] Using sample data (data/sample/) — expected runtime < 30 seconds..."
    python -m src.rebuild_pipeline --source sample
    ;;
  *)
    echo "[run] Using full raw data (data/raw/) — expected runtime 8–15 minutes..."
    python -m src.rebuild_pipeline
    ;;
esac

echo ""
echo "[run] Pipeline complete. Outputs written to outputs/"
echo "[run] Running test suite..."
python -m pytest tests/ -v
