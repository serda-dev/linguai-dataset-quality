#!/usr/bin/env bash
set -euo pipefail

cd /workspace/linguai-dataset-quality
mkdir -p /workspace/linguai-classification
exec > >(tee -a /workspace/linguai-classification/job.log) 2>&1

for source_id in bella-akademik bella-ozenli cosmos bella-oscar mogan bella-mc4 fineweb2-tur; do
  echo "$(date -u +%FT%TZ) starting $source_id" >&2
  /venv/main/bin/python scripts/classify_student_stream.py \
    --source-id "$source_id" \
    --output-dir "/workspace/linguai-classification/$source_id" \
    --batch-size 128 --prefetch-batches 3 --part-rows 100000 --device cuda
  echo "$(date -u +%FT%TZ) completed $source_id" >&2
done

date -u +%FT%TZ > /workspace/linguai-classification/ALL_DONE
