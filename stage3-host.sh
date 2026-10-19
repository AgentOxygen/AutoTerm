#!/bin/bash
# Stage 3 (Dockerfile.stage3) on the host's GPU: builds the images, checks that the GPU is usable
# from Docker, runs the author's driver, and then checks the outputs. The exit code means little
# here, because every failure in this pipeline exits 0.
# Run it from anywhere on the host. It is not meant for the sandbox, which has no GPU.
#
#   ./stage3-host.sh [--cpu] [checkpoint.tar] [data_dir]
#
#   checkpoint.tar  default downloads/drn54_May5_2022_0.001_batch16_keep_augmentation.tar.
#                   Outputs go to directories named after it, so runs with different checkpoints
#                   (for example downloads/enze/Front_DL3/drn54_Mar8_2022_...tar) sit side by side.
#   data_dir        default tier-c/data, the stage 2 output (Dockerfile.preprocess).
#   --cpu           use the CPU image instead (the sandbox's way to test this script).
#
# Host requirements for the GPU: an NVIDIA driver that supports CUDA 13.0 (R580 or newer; the GPU
# image uses torch 2.14.0+cu130), and the NVIDIA Container Toolkit, so that `docker run --gpus all`
# works. About 15 GB of free Docker storage for the CUDA torch image.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

device=cuda
if [ "${1:-}" = --cpu ]; then device=cpu; shift; fi
ckpt=$(readlink -f "${1:-downloads/drn54_May5_2022_0.001_batch16_keep_augmentation.tar}")
data=$(readlink -f "${2:-tier-c/data}")
net=$(basename "$ckpt")
temp=${net%.tar*}
[ -f "$ckpt" ] || { echo "checkpoint not found: $ckpt" >&2; exit 1; }
ls -d "$data"/GID*/GID_* >/dev/null 2>&1 || { echo "no stage 2 output under $data" >&2; exit 1; }

if [ $device = cuda ]; then
	base=frontdl3; base_df=Dockerfile.frontdl3; image=autoterm-stage3-gpu; gpus=(--gpus all)
else
	base=frontdl3-cpu; base_df=Dockerfile.frontdl3-cpu; image=autoterm-stage3; gpus=()
fi

echo "== build ($device)"
docker build -q -f $base_df -t $base . >/dev/null
docker build -q -f Dockerfile.stage3 --build-arg BASE=$base --build-arg DEVICE=$device -t $image . >/dev/null

if [ $device = cuda ]; then
	echo "== GPU preflight"
	# The container must see the GPU, and this torch build must have kernels for its architecture
	# (sm_120 for the RTX 5070). Otherwise inference fails on the first patch, or falls back silently.
	docker run --rm "${gpus[@]}" --entrypoint python $image -c "
import torch
assert torch.cuda.is_available(), 'CUDA not available in the container: check the NVIDIA driver and nvidia-container-toolkit'
cap = torch.cuda.get_device_capability(0); arch = 'sm_%d%d' % cap
assert arch in torch.cuda.get_arch_list(), (arch, torch.cuda.get_arch_list())
x = torch.randn(512, 512, device='cuda'); float((x @ x).sum())
print('GPU ok:', torch.cuda.get_device_name(0), arch, '| torch', torch.__version__, 'cuda', torch.version.cuda)"
fi

mkdir -p tier-c
log=tier-c/stage3-$device-$temp.log
echo "== run: $net on $data (log: $log)"
start=$(date +%s)
docker run --rm "${gpus[@]}" \
	-v "$data:/home/staff/enze/data1/Greenland_front_Mapping/data" \
	-v "$ckpt:/home/staff/enze/Front_DL3/$net:ro" \
	$image bash batch_inference_plot_mv_figure_dir.sh "$net" > "$log" 2>&1 || true
echo "   took $(( ($(date +%s) - start) / 60 )) min"

# The container runs as root. Give the outputs back to the invoking user.
docker run --rm -v "$data:/d" --entrypoint chown $image -R "$(id -u):$(id -g)" /d

echo "== output check"
fail=0
count() { if [ -d "$1" ]; then find "$1" -maxdepth 1 -name "$2" | wc -l; else echo 0; fi; }
for g in "$data"/GID*; do
	for s in "$g"/GID_*; do
		inp=$(count "$s/upsample" '*.tif'); gmt=$(count "$s/in_polygon_gmt/$temp" '*.gmt')
		tr=$(count "$s/truncate_termini/$temp" '*.gmt'); ab=$(count "$s/truncate_termini/$temp/abandon" '*.gmt')
		printf '%-28s images %4d  traces %4d  truncated %4d  screened out %4d\n' "$(basename "$s")" "$inp" "$gmt" "$tr" "$ab"
		[ "$inp" -gt 0 ] && { [ "$gmt" -eq 0 ] || [ "$tr" -eq 0 ]; } && fail=1
	done
	fin=$(count "$g/truncate_termini/$temp" '*.gmt'); fab=$(count "$g/truncate_termini/$temp/abandon" '*.gmt')
	printf '%-28s final traces %4d  removed by area screening %4d\n' "$(basename "$g")" "$fin" "$fab"
	[ "$fin" -eq 0 ] && fail=1
done
echo "== log problems (counts)"
grep -oE 'command not found|No module named [^ ]+|Traceback|unary operator expected|integer expression expected|CUDA error[^.]*' "$log" \
	| sort | uniq -c || echo "   none"
[ $fail = 0 ] && echo "RESULT: outputs present" || { echo "RESULT: FAILED, a stage produced no output" >&2; exit 1; }
