# Running and verifying

How to execute code in this repository and how to check that a change worked.

## What can actually be run today

| Target | Runnable | How |
|---|---|---|
| FrontDL3 inference stage | Yes | `Dockerfile.frontdl3` (GPU, cu130) or `Dockerfile.frontdl3-cpu`, described below |
| Individual `data_processing/` Python helpers | Yes | Direct invocation with `--input` and `--output` |
| Root `batch_inference_termini/` stage 3 driver | **Yes** | `Dockerfile.stage3`. See "Stage 3 in a container" below. CPU smoke test verified every step; the full GID278 GPU run is pending |
| Stage 2 preprocessing | **Yes** | `Dockerfile.preprocess` (ubuntu:18.04, which still packages `gdal_contrast_stretch`). Done for GID278, all four sensors |
| Stage 1 download | Yes, on the host | Needs Google Earth Engine credentials, so it runs bare-metal (`.env/` venv) or through `Dockerfile.gee-download`. Earth Engine auth fails inside the sandbox. ROI boxes for all 295 glaciers are in `downloads/Glacier Identification.csv` |
| Training | Partly | The TermPicks label set is in `downloads/label_shape_TermPicks.zip`. Source imagery is not included, and the paper's run took 120 GB of GPU memory over 5 to 7 days |
| `src/autoterm` | No | Stub, see `refactor-target.md` |

There is no test suite, no continuous integration, and no dependency manifest. `pyproject.toml`
declares an empty `dependencies` list. The root `Dockerfile` is zero bytes.

There is, however, a reference dataset: `downloads/Termini.zip` holds the published output for all
295 glaciers. See "How to verify a change" below.

## The verified path: FrontDL3 inference in a container

`Dockerfile.frontdl3` at the repository root builds a working reproduction of the segmentation
stage. Read that file before doing any environment work. Its header comment records the result of
the run it was written for: 28 patches producing one terminus trace of 814 points for Jakobshavn
Isbrae.

Build. The build context is unused because the source is cloned inside the image:

```
docker build -f Dockerfile.frontdl3 -t frontdl3 .
```

Run. The checkpoint is mounted rather than baked into the image, because it is about 326 MB:

```
docker run --rm --gpus all \
  -v /path/to/drn54_May5_2022_0.001_batch16_keep_augmentation.tar:/Front_DL3/network.tar:ro \
  -v "$PWD/out:/out" frontdl3 bash -c \
  'bash preparing_influence.sh /Front_DL3/train \
   && bash exe_inference.sh /Front_DL3/polygon/cut_polygon.gmt network.tar \
   && cp -r /Front_DL3/in_polygon_gmt /out/'
```

What the image does and why each piece is needed:

| Decision | Reason |
|---|---|
| Base image `ghcr.io/osgeo/gdal:ubuntu-small-latest` | Puts the GDAL command line tools and the `osgeo` Python bindings in the same interpreter as `torch`. `gdal_merge_average.py` needs `from osgeo import gdal` and `inference.py` needs `import torch` |
| PyTorch 2.14.0 from the cu130 index | The target GPU is sm_120 (needs CUDA >= 12.8). cu130 carries the same torch version as the pinned CPU image; the cu128 channel stops at 2.11. Host driver R580+ |
| Symlink `python2` to `python3` | The shell scripts invoke `python2 parameters.py`. The script itself is Python 3 clean |
| Upstream pinned to commit `5684a19` | Keeps the baseline fixed if upstream moves |
| `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` | PyTorch 2.6 and later default `torch.load` to `weights_only=True`, which rejects the 2022 checkpoint |
| Five `sed` patches applied at build time | Documented inline in the Dockerfile. Each corresponds to a fix listed in `repository-map.md` |

### The Dockerfile and the submodule overlap

`Dockerfile.frontdl3` clones `github.com/enzezhang/FrontDL3` and patches it with `sed` at build
time. The `FrontDL3/` submodule is a fork of the same upstream with those same fixes committed as
real commits, plus CPU support and `set -euo pipefail` in the shell scripts.

These are two ways of reaching nearly the same state. If you are changing the container build,
consider building from the submodule instead of cloning upstream, which removes the `sed` patches
and gives version-controlled fixes. That change has not been made; the Dockerfile still clones
upstream.

### Running without a GPU

The submodule fork makes `--cuda` optional in `inference.py`, so inference runs on CPU. The root
copy at `pytorch-deeplab-xception/inference.py` calls `.cuda()` unconditionally and has no CPU path.

This environment has no NVIDIA driver, so `--gpus all` will not work here. Use the submodule's CPU
path for any local verification.

## Running an individual helper

Scripts in `data_processing/` are small single-purpose command line tools. Most take `--input`,
some take `--output`, `--date`, or `--polygon`. They read and write two-column GMT ASCII.

Example, measuring the length of a trace in metres:

```
python data_processing/cal_length.py --input <trace>.gmt --date 20160302
```

This prints `<date> <length_in_metres>`. It reprojects to polar stereographic before measuring, so
the output is metres, not degrees.

These helpers are the cheapest way to verify a geometry change, because they have no dependency on
`para.ini`, on the directory layout, or on a checkpoint.

## How to verify a change

There is still no test suite, but there is now a reference dataset. Use the strongest of these that
applies.

1. **Compare against the published traces.** `downloads/Termini.zip` holds complete shapefile sets
   for all 295 glaciers, the published 278,239 traces. For a glacier you have run, match output to
   `Termini/GID<n>.shp` on the `Date` and `Satellite` attributes, then measure deviation with the
   paper's own metric, enclosed area divided by trace length, already implemented in
   `data_processing/calculate_error.py`. Expect figures near the paper's: 79 m test error before
   screening, 62 m after, 37 m average duplicate-trace uncertainty. This is the strongest check
   available and the one the whole project depends on.
2. Run the container reproduction end to end and compare the output trace to the recorded result
   of 814 points for Jakobshavn Isbrae.
3. Run the specific `data_processing/` helper you changed on a known input and compare numbers.
4. For a shell script change, run `bash -n <script>` to check syntax, then read the call sites. The
   scripts have almost no error handling, so a wrong path produces empty output rather than a
   failure.
5. For a Python change, import the module and confirm it imports. Several modules in
   `basic_src/` do not import on Python 3 at all; confirm the baseline before blaming your change.
6. Check that file name fields survive. Much of the pipeline parses dates and sensors out of file
   names with `cut -d '_'`, so a renamed output silently corrupts downstream metadata rather than
   erroring.

## Stage 3 in a container

`Dockerfile.stage3` assembles the author's working-root layout at `/home/staff/enze/Front_DL3` and
runs the repo's `batch_inference_termini/` scripts unmodified. Build it on the GPU or the CPU base:

```bash
docker build -f Dockerfile.frontdl3 -t frontdl3 .                      # GPU base (cu130, host driver R580+)
docker build -f Dockerfile.stage3 --build-arg BASE=frontdl3 --build-arg DEVICE=cuda -t autoterm-stage3-gpu .
docker build -f Dockerfile.frontdl3-cpu -t frontdl3-cpu .              # CPU base
docker build -f Dockerfile.stage3 -t autoterm-stage3 .
```

**Full run** (all sensors, then truncation, screening, duplicates, the S1 offset and error). Mount
the scratch directories on the host: each patch is an uncompressed 693 KB GeoTIFF, about 70 GB at
peak for GID278.

```bash
mkdir -p tier-c/scratch/test_output tier-c/scratch/post_output
docker run --rm --gpus all \
  -v "$PWD/tier-c/data:/home/staff/enze/data1/Greenland_front_Mapping/data" \
  -v "$PWD/downloads/<checkpoint>.tar:/home/staff/enze/Front_DL3/<checkpoint>.tar:ro" \
  -v "$PWD/tier-c/scratch/test_output:/home/staff/enze/Front_DL3/test_output" \
  -v "$PWD/tier-c/scratch/post_output:/home/staff/enze/Front_DL3/post_output" \
  autoterm-stage3-gpu bash batch_inference_plot_mv_figure_dir.sh <checkpoint>.tar 2>&1 | tee tier-c/stage3.log
```

`./stage3-host.sh [--cpu] [checkpoint] [data_dir]` wraps the builds, a GPU preflight, the run, a
`chown`, and an output-count check.

**Single image, inference only** (about 10 s on the RTX 5070, 4 min on the sandbox CPU). `${IMG:?}`
stops an empty variable from mounting the whole folder:

```bash
IMG=20140827_Landsat8_GID278_stretch.tif
docker run --rm --gpus all \
  -v "$PWD/tier-c/data/GID278/GID_278_Landsat-8/upsample/${IMG:?set IMG first}:/in/$IMG:ro" \
  -v "$PWD/tier-c/data/GID278/polygon:/polygon:ro" \
  -v "$PWD/downloads/<checkpoint>.tar:/home/staff/enze/Front_DL3/network.tar:ro" \
  -v "$PWD/tier-c/single:/out" \
  autoterm-stage3-gpu bash -c 'bash preparing_influence.sh /in && bash exe_inference.sh /polygon/GID_278_cutting_polygon_shrink.gmt network.tar && cp -r in_polygon_gmt /out/'
```

**Checks after a run** (the exit code means nothing here):

- Per sensor, `upsample/*.tif` should equal `in_polygon_gmt/<ckpt>/*.gmt` (one trace per image).
- `truncate_termini/<ckpt>/` plus `abandon/` should hold every trace. Truncation is a pass-through for
  GID278 (no bed polygons), so truncated traces equal their inputs.
- `GID<n>/truncate_termini/<ckpt>/` holds the final set.
- Grep the log for `command not found`, `No module named`, `unary operator expected` and `CUDA error`.
  The expected noise is `ls … bed_GID*_??.gmt`, `rm`/`mkdir` messages about the scratch mounts, and one
  `find_min_max.py` IndexError (figure only).
- Look at the result in `tools/data_viewer` (its README has the commands).

**Measured:** CPU 1.06 s per 960x720 patch; RTX 5070 about 20 patches/s. 198 patches per Landsat-8
image and 112 per Sentinel image, about 249k for GID278. Each patch costs 982 GFLOP (FlopCounterMode). GPU
and CPU traces agree to within one pixel (TF32); `-e NVIDIA_TF32_OVERRIDE=0` makes them identical.

### Golden reference (smallest reproducible case)

`golden/` holds byte-for-byte reference outputs for two fixed GID278 subsets (8 and 24 images, May5
checkpoint), with `golden/verify-golden.sh <8|24> <data dir>` and `./gpu-smoke.sh [8|24]` (host GPU run
plus verification). Read `golden/README.md`. Use it before any full run, and as the integrity check
for v2. Run with `NVIDIA_TF32_OVERRIDE=0` on a GPU for a byte-exact match.

### Stage 3 under Apptainer (the 8× L40S cluster)

The cluster runs containers only through Apptainer `.sif` files. **Verified 2026-10-07** in the
sandbox (Apptainer 1.4.5, `.sif` built from the CPU `autoterm-stage3`, the same 8 images as
`tier-c/smoke-script/`): every driver step ran, and all 58 trace/text outputs were byte-identical
to the Docker run. Same log noise, plus one Ghostscript `Error: /undefined in A`, which the Docker
smoke run also had.

Three things differ from Docker, and the commands below handle each one:

1. **The image is read-only.** The driver writes into its working root (`list/`, `post_process_*`,
   `in_polygon_gmt`, `gmt.conf`), so the working root is copied out of the `.sif` once and bound
   back over itself. The copy is the image's own files, unchanged.
2. **`WORKDIR` is ignored.** Without `--pwd` the driver starts in `$HOME` and cannot find `para.ini`.
3. **Host environment leaks in.** `--cleanenv --containall` keeps cluster modules (`PYTHONPATH`,
   `LD_LIBRARY_PATH`) and `$HOME` out.

**The L40S machine needs its own image.** Its driver is 570.207 (CUDA 12.8 at most), so the cu130
image cannot start there. `TORCH_CUDA=cu126` builds the same torch 2.14.0 and torchvision 0.29.0
for CUDA 12.6 (kernels sm_50 to sm_90; the L40S is sm_89 and runs the sm_86 code). That build cannot
target the RTX 5070, so the 5070 keeps the cu130 image. Build on the host, because the sandbox can't
reach `pypi.nvidia.com`:

```bash
docker build -f Dockerfile.frontdl3 --build-arg TORCH_CUDA=cu126 -t frontdl3-cu126 .
docker build -f Dockerfile.stage3 --build-arg BASE=frontdl3-cu126 --build-arg DEVICE=cuda \
  --build-arg GPU_ARCH=sm_89 -t autoterm-stage3-gpu-cu126 .
apptainer build autoterm-stage3-gpu-cu126.sif docker-daemon://autoterm-stage3-gpu-cu126:latest
# or, without apptainer on the host: docker save autoterm-stage3-gpu-cu126 -o stage3-gpu-cu126.tar,
# copy it over, then: apptainer build autoterm-stage3-gpu-cu126.sif docker-archive://stage3-gpu-cu126.tar
```

Run one checkpoint. Each run needs its **own copy of the data**, because the driver writes
non-namespaced files into it (for example `truncate_termini/temp.txt`). Stage 3 never reads
`after_merge/`, so leaving it out cuts the GID278 upload from 39 GB to about 11 GB
(`rsync -a --exclude after_merge tier-c/data/ <dest>/`).

```bash
SIF=$PWD/autoterm-stage3-gpu-cu126.sif
CKPT=drn54_May5_2022_0.001_batch16_keep_augmentation.tar
RUN=$PWD/run-May5                    # holds data/ (the copy), work/, scratch/
mkdir -p "${RUN:?}/work" "$RUN/scratch/test_output" "$RUN/scratch/post_output"
apptainer exec --containall --bind "$RUN/work:/mnt" "${SIF:?}" cp -a /home/staff/enze/Front_DL3/. /mnt/
mkdir -p "$RUN/work/test_output" "$RUN/work/post_output"     # mount points for the scratch binds
cp "${CKPT:?}" "$RUN/work/"
apptainer exec --nv --cleanenv --containall \
  --bind "$RUN/data:/home/staff/enze/data1/Greenland_front_Mapping/data" \
  --bind "$RUN/work:/home/staff/enze/Front_DL3" \
  --bind "$RUN/scratch/test_output:/home/staff/enze/Front_DL3/test_output" \
  --bind "$RUN/scratch/post_output:/home/staff/enze/Front_DL3/post_output" \
  --pwd /home/staff/enze/Front_DL3 \
  "$SIF" bash batch_inference_plot_mv_figure_dir.sh "$CKPT" > "$RUN/run.log" 2>&1
```

- **GPU selection: the `BASH_ENV` pin (verified 2026-10-07).** `exe_inference.sh` line 3 sets
  `CUDA_VISIBLE_DEVICES=0` itself. The L40S machine has no scheduler, plain `--nv` exposes all 8 GPUs
  (even with `--contain`), and `nvidia-container-cli` (needed for `--nvccli` isolation) is not
  installed. So the run puts a one-line file in the working root and points `BASH_ENV` at it.
  Every non-interactive bash reads that file first, so the variable is read-only by the time line 3
  runs: the export fails with `CUDA_VISIBLE_DEVICES: readonly variable` (log noise, once per batch),
  and the script continues on the chosen GPU. No source file changes; only which identical GPU runs
  the job. Checked on the node (torch saw 1 device, UUID of physical GPU 3), and on CPU: the
  8-image Apptainer run with `BASH_ENV` was byte-identical (99 files) to the run without it, and to
  Docker's (58 trace/text files). Add to the setup and the run:

  ```bash
  echo "readonly CUDA_VISIBLE_DEVICES=${GPU:?}; export CUDA_VISIBLE_DEVICES" > "$RUN/work/gpu-select.sh"
  # in the apptainer exec line:
  #   --env BASH_ENV=/home/staff/enze/Front_DL3/gpu-select.sh
  ```
- **Parallelism.** One glacier is one serial driver run. Do not split it by sensor: screening counts
  abandonments across all four sensors, and the Sentinel-1 test borrows Sentinel-2's IQR. The 8 GPUs
  help by running checkpoints (and later glaciers) side by side.
- Files are written as the calling user, so no `chown` is needed.

## Failure modes that do not raise

These produce empty or wrong output with a success exit code. Check for them explicitly.

| Situation | Symptom |
|---|---|
| Glacier has no cutting polygon | Stage 3 prints "no cutting polygon" and skips the glacier |
| `upsample/` is empty | Stage 3 silently falls back to `hist_eq/` |
| Wrong path in a `batch_*.sh` script | Empty result directory, exit code 0 |
| `parameters.py` cannot find a key | Empty string captured into a shell variable, used as a path |
| File name has the wrong number of underscore fields | Wrong date or sensor recorded, no error |
| `sed -i 1,11d` on a GMT file whose header length changed | Data rows removed or header lines retained |
| `bc` missing from the image | Every screening comparison errors, so nothing is abandoned |
| `data_processing/` not on `PATH` | Step scripts can't find helpers called by bare name; screening and merging silently skip |
| Docker storage full during inference | Patch GeoTIFF writes fail, and traces are built from missing patches |
| Empty shell variable in a `-v` path | The whole parent folder is mounted (e.g. all 353 images instead of one) |

The submodule's `exe_inference.sh` adds `set -euo pipefail`, which converts some of these into real
failures. The root copy does not have it.

## Environment notes for this sandbox

- Persistent environment variables go in `/etc/sandbox-persistent.sh`, which is sourced before
  every Bash command. Never add shell completion scripts to it.
- Network access is filtered. A blocked request returns HTTP 403 with a structured body explaining
  which rule blocked it.
- Google Earth Engine stage 1 needs `ee.Authenticate()` and an account, so it cannot run
  unattended here.
