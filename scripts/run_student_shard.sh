#!/usr/bin/env bash
set -euo pipefail

gpu=${1:?GPU index required}
[[ $gpu =~ ^[0-3]$ ]] || { echo "Invalid GPU index: $gpu" >&2; exit 2; }
export CUDA_VISIBLE_DEVICES=$gpu
cd /workspace/linguai-dataset-quality
root=/workspace/linguai-classification
mkdir -p "$root"
exec > >(tee -a "$root/job-gpu${gpu}.log") 2>&1

run_source() {
  local source_id=$1 output_id=$2
  shift 2
  echo "$(date -u +%FT%TZ) GPU $gpu starting $output_id" >&2
  /venv/main/bin/python scripts/classify_student_stream.py \
    --source-id "$source_id" --output-dir "$root/$output_id" \
    --batch-size 128 --prefetch-batches 3 --part-rows 100000 --device cuda "$@"
  test -f "$root/$output_id/DONE.json"
  echo "$(date -u +%FT%TZ) GPU $gpu completed $output_id" >&2
}

case $gpu in
  0) run_source fineweb2-tur fineweb2-tur-files-00-14 --file-start 0 --file-end 14 ;;
  1) run_source fineweb2-tur fineweb2-tur-files-14-30 --file-start 14 --file-end 30 ;;
  2) run_source bella-mc4 bella-mc4 ;;
  3)
    run_source bella-ozenli bella-ozenli
    run_source cosmos cosmos
    run_source bella-oscar bella-oscar
    run_source mogan mogan
    ;;
esac

date -u +%FT%TZ > "$root/GPU${gpu}_DONE"
