#!/usr/bin/env bash
set -euo pipefail

training_root=/home/serda/.local/share/linguai-training
output_dir="$training_root/run-20261003"
mkdir -p "$output_dir"
chmod 700 "$output_dir"
exec 9>"$output_dir/train.lock"
flock -n 9 || exit 0
if [[ -s "$output_dir/student_model.safetensors" ]]; then
    echo "TRAINING_DONE: model artifact exists"
    exit 0
fi
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=6
cd /home/serda/linguai-dataset-quality
exec "$training_root/venv/bin/python" scripts/train_student.py \
    --data "$training_root/data/labels.parquet" \
    --model-dir "$training_root/base-model" \
    --output-dir "$output_dir" \
    --epochs 1 --batch-size 8 --max-length 512 \
    --unfreeze-layers 2 --checkpoint-every 300
