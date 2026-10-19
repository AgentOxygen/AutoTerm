#!/usr/bin/env bash
# Stage 3 smoke run on the host GPU, then a byte-for-byte check against golden/.
# Run from the repo root, on the host: ./gpu-smoke.sh [24|8]
#   24 (default): 6 images per sensor, the screening tier (inputs tier-c/smoke)
#    8: 2 images per sensor, the fast tier (inputs tier-c/smoke-script)
# Needs the image autoterm-stage3-gpu and downloads/drn54_May5_2022_...tar (both already on the host).
# Output: tier-c/gpu-smoke-<tier>/ and tier-c/gpu-smoke-<tier>.log.
set -euo pipefail
cd "$(dirname "$0")"

TIER=${1:-24}
case "$TIER" in 24) SRC=tier-c/smoke;; 8) SRC=tier-c/smoke-script;; *) echo "usage: $0 [24|8]" >&2; exit 1;; esac
CKPT=drn54_May5_2022_0.001_batch16_keep_augmentation.tar
OUT=tier-c/gpu-smoke-$TIER
LOG=tier-c/gpu-smoke-$TIER.log
SENSORS="Landsat-8 Sentinel-2 Sentinel-1_D Sentinel-1_A"

[ -f "downloads/${CKPT:?}" ] || { echo "missing downloads/$CKPT" >&2; exit 1; }
[ -d "$SRC/data/GID278" ] || { echo "missing $SRC/data/GID278" >&2; exit 1; }

# 1. Clean copy of the smoke inputs with the old CPU outputs removed, so stale files cannot mask a failure
rm -rf "${OUT:?}"
mkdir -p "$OUT"
cp -a "$SRC/data" "$OUT/data"
rm -rf "$OUT/data/GID278/truncate_termini"
for s in $SENSORS; do
	d="$OUT/data/GID278/GID_278_$s"
	rm -rf "$d"/{in_polygon_gmt,truncate_termini,post_process_shape,after_merge,figure,truncate_figure,temp}
done
mkdir -p "$OUT/test_output" "$OUT/post_output"

# 2. Run (TF32 off, so the traces should match the CPU ones more closely)
docker run --rm --gpus all -e NVIDIA_TF32_OVERRIDE=0 \
	-v "$PWD/$OUT/data:/home/staff/enze/data1/Greenland_front_Mapping/data" \
	-v "$PWD/downloads/$CKPT:/home/staff/enze/Front_DL3/$CKPT:ro" \
	-v "$PWD/$OUT/test_output:/home/staff/enze/Front_DL3/test_output" \
	-v "$PWD/$OUT/post_output:/home/staff/enze/Front_DL3/post_output" \
	autoterm-stage3-gpu \
	bash batch_inference_plot_mv_figure_dir.sh "$CKPT" \
	2>&1 | tee $LOG

# 3. The container writes as root: give the files back
sudo chown -R "$(id -u):$(id -g)" "$OUT" $LOG

# 4. Sanity check: counts per sensor, final set, and error strings in the log
echo
for s in $SENSORS; do
	d="$OUT/data/GID278/GID_278_$s"
	printf '%-14s images %s, traces %s\n' "$s" "$(ls "$d"/upsample | wc -l)" \
		"$(ls "$d"/in_polygon_gmt/*/*.gmt 2>/dev/null | wc -l)"
done
echo "final set:"
ls "$OUT"/data/GID278/truncate_termini/*/ | head -50
echo "error strings in log (want 0): $(grep -c -E 'command not found|No module named|unary operator expected|CUDA error' $LOG || true)"
echo
expected_files=$(find golden/golden-$TIER -type f | wc -l)
golden/verify-golden.sh "$TIER" "$OUT/data" || { echo "run does NOT match golden-$TIER ($expected_files files expected)" >&2; exit 1; }
