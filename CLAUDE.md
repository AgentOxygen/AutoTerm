# AutoTerm

## What this project is

AutoTerm is a published research pipeline that extracts glacier terminus traces from satellite
imagery of Greenland (Zhang, Catania, Trugman, 2023, The Cryosphere 17, 3485-3503). The code in
this repository is the research code behind that paper.

## Goal and strategy

The objective is **AutoTerm v2**. Getting there has two phases.

**Phase 1, current: reproduce the original pipeline in a Docker container, with as few changes to
the source code as possible.**

**Phase 2, later: build v2, using the reproduced pipeline's output as the reference** that proves
accuracy is preserved, and as the baseline for performance benchmarking.

The reproduction is not throwaway scaffolding. It is the measuring instrument for everything that
follows. If the reproduction silently differs from the original, every v2 accuracy claim measured
against it is wrong.

## Resume here (last updated 2026-10-05)

Work is tracked step by step in `IMPLEMENTATION_PLAN.md`, Tier C. Read its C1d, "C2, evidence", "C2c
findings" and C3 entries before doing anything. The glacier is **GID278 (Jakobshavn)**. Tiers A and B,
stage 1 (download), stage 2 (preprocessing) and the stage 3 image are done.

**Waiting on the user: the full stage 3 GPU run on the host (RTX 5070).** It is started by the user, not
from the sandbox. Run from the repo root on the host (the images are already built there):

```bash
mkdir -p tier-c/scratch/test_output tier-c/scratch/post_output
docker run --rm --gpus all \
  -v "$PWD/tier-c/data:/home/staff/enze/data1/Greenland_front_Mapping/data" \
  -v "$PWD/downloads/drn54_May5_2022_0.001_batch16_keep_augmentation.tar:/home/staff/enze/Front_DL3/drn54_May5_2022_0.001_batch16_keep_augmentation.tar:ro" \
  -v "$PWD/tier-c/scratch/test_output:/home/staff/enze/Front_DL3/test_output" \
  -v "$PWD/tier-c/scratch/post_output:/home/staff/enze/Front_DL3/post_output" \
  autoterm-stage3-gpu \
  bash batch_inference_plot_mv_figure_dir.sh drn54_May5_2022_0.001_batch16_keep_augmentation.tar \
  2>&1 | tee tier-c/stage3-gpu-May5.log
sudo chown -R $USER: tier-c     # afterwards: the container writes as root
```

- About 249,300 patches at the measured **~20 patches/s on the 5070**: about 3.5 h of inference, plus
  CPU post-processing. Expect 4–6 h. The progress counter restarts for every batch of 50 images.
- The two `tier-c/scratch` mounts matter: each patch is an uncompressed 693 KB GeoTIFF, so the run peaks
  at about 70 GB of scratch. Inside Docker's storage, a full disk fails the patch writes silently.
- Harmless log noise: `rm: cannot remove 'test_output': Device or resource busy` and `mkdir: … File
  exists` (from the mounts), `ls: cannot access '…bed_GID278_??.gmt'` (no bed polygons, by design), and
  one `find_min_max.py` IndexError (figure only).
- `./stage3-host.sh` does the same, plus a GPU preflight and an output-count check. The user found it
  too complex, so they run the plain commands above. Keep both working.
- A user's first "single image" attempt ran all 353 Landsat images: `$IMG` was empty, so the whole
  folder was mounted. The single-image command in `docs/llm/running-and-verifying.md` guards this with
  `${IMG:?}`.

**When the run finishes, in order:**

1. **Check outputs, not the exit code.** Count per sensor: `upsample/` images vs
   `in_polygon_gmt/<ckpt>/` vs `truncate_termini/<ckpt>/` (+`abandon/`), plus the final set in
   `GID278/truncate_termini/<ckpt>/`. Expected inputs: L8 353, S2 470, S1-D 700, S1-A 432 images.
   Scan the log for `command not found`, `No module named`, `unary operator expected` and `CUDA error`.
   `tools/data_viewer` shows all of this in a browser (see below).
2. **C4:** compare against the 693 published GID278 traces (`downloads/Termini.zip`: Landsat8 188,
   Sentinel2 255, Sentinel1 250), matched on Date + Satellite, using `data_processing/calculate_error.py`'s
   enclosed-area/length metric. Restrict to the published windows (L8/S2 to 2021-10, S1 to 2022-02).
   The paper's figures are 79 m test error before screening, 62 m after, and 37 m between duplicates. Check
   the 7 published dates where a midnight-sun Landsat scene was merged over a day scene. The published S1
   traces include the author's offset correction (`batch_calculate_offset_sentinel.sh`).
3. **Checkpoint question:** repeat the run with `downloads/enze/Front_DL3/drn54_Mar8_2022_0.001_batch16_keep_augmentation.tar`
   (the checkpoint every March 2023 production run used). Outputs go in folders named after the
   checkpoint, so the runs sit side by side. The one that matches the published traces better is the
   answer.
4. Tier D (MC dropout, merge, format check) only after C4 gives numbers in the expected range.

**Decisions made 2026-10-05 (user-approved, evidence in `IMPLEMENTATION_PLAN.md`):**
- **No bedrock polygons for GID278.** The published traces were never truncated at the fjord walls
  (90% of endpoints lie within 32 m of the cutting box), and `truncate_termini.py` passes traces through
  unchanged when no `bed_*.gmt` exists. This replaces the 2026-09-30 plan to derive polygons; C2 is
  not needed.
- **Driver:** the repo's `batch_inference_termini/` copy (3 screening iterations, as in the author's
  March 2023 logs), not the author's later working copy (2 iterations, plus flowline-intersection
  screening that needs assets found in no archive).
- **Cutting polygon:** stage 2's `GID_278_cutting_polygon_shrink.gmt`, the one the author used for GID278.
- **Checkpoint:** `May5_2022` first, then `Mar8_2022` for comparison.
- **Scope (user, 2026-10-05): focus on reproducing inference results only.** Training (T0–T3 in the
  conversation: rebuild the 21,923-label training set from `label_shape_TermPicks.zip`, retrain on the
  user's 8× L40S, then swap architectures) is parked until the reproduction is verified.

**Verified so far (stage 3):** the CPU smoke test (`tier-c/smoke/`, 24 images, every driver step) gave
traces within a 36 m median of the published ones. The pinned images reproduce those traces
bit-identically. A single-image GPU run on the 5070 matched the CPU trace to within one pixel (3,162 of
3,320 points identical; the rest moved by at most 7.31 m, one pixel, from TF32 convolutions;
`-e NVIDIA_TF32_OVERRIDE=0` would make them exact). Sample figure: `tier-c/sample-traces-GID278.png`.

**Viewer:** `tools/data_viewer/` (see its README) is a read-only web app showing per-date status, the
image, raw/final/published traces, and an overview. It works on any stage 2/3 data folder:
`docker build -t autoterm-viewer tools/data_viewer && docker run --rm -p 127.0.0.1:8080:8080 -v
"$PWD/tier-c/data:/data:ro" -v "$PWD/downloads/Termini.zip:/published/Termini.zip:ro" autoterm-viewer`.
Its API is tested, but it has never been rendered in a browser yet (the sandbox can't download one). Get
the user's feedback on the first real view.

**Traps found so far, all exiting 0:**
- Stage 2 silently skips glaciers with no Landsat-8.
- Stage 2 takes the Landsat-8 grid size from whichever scene lists first, which can be a partial edge
  clip (`Dockerfile.preprocess` deviation 2).
- A missing `gdal_merge.py` deletes every multi-scene date.
- Truncation without `intersect.py` crashes on import for every trace.
- Without `bc`, screening abandons nothing.
- Stage 3 helpers are called by bare name and found only through `PATH` (`Front_DL3/data_processing`).
- The committed GEE script never finishes (missing `readline()`).
- An empty shell variable in a `-v` path mounts a whole folder.
- `ubuntu-small-latest` is a nightly GDAL dev build, which silently replaced a verified image.
- Patch scratch inside Docker can fill the disk.

`Dockerfile.preprocess` and `Dockerfile.stage3` now fail their builds if any required tool is missing.

## The current task

Reproduce one end-to-end AutoTerm workflow: satellite images in, screened terminus traces out, for
at least one glacier.

`Dockerfile.frontdl3` already reproduces the segmentation stage alone, verified at 28 patches
producing one 814-point trace for Jakobshavn Isbrae. End-to-end means going beyond that to the full
stage 3 pipeline in `batch_inference_termini/`, which adds truncation, screening, duplicate removal,
the Sentinel-1 offset correction, and error calculation.

Read `docs/llm/reproduction-plan.md` before starting. It breaks the work into tiers and identifies
the one asset that blocks the tier that matters. Two points from it belong here:

1. The 76 hardcoded paths collapse to two roots. Mounting `downloads/enze/Front_DL3` at
   `/home/staff/enze/Front_DL3` satisfies 59 of them with no source edits, because it is already
   the layout the scripts expect.
2. Truncation output must exist for screening to do anything. With `intersect.py` vendored,
   `truncate_termini.py` writes traces through unchanged when no bedrock polygon exists, which
   matches the published GID278 traces (see Resume here). In general, verify by checking for output
   files, never by checking exit codes.
3. Verification is now possible. `downloads/Termini.zip` holds the published traces for all 295
   glaciers, so reproduction output can be compared numerically against the real thing.

Do not start work on v2 until an end-to-end run produces output.

## The minimal-modification rule

This constraint drives most day-to-day decisions, and it inverts the usual instinct.

**Do not refactor the source to make it run. Change the environment so the unmodified source runs.**

| Problem | Wrong response | Right response |
|---|---|---|
| 76 hardcoded paths to `/home/staff/enze/...` | Edit 45 files to use relative paths | Recreate that path inside the container, with a bind mount, symlink, or `WORKDIR` |
| Shell scripts call `python2` | Edit 13 call sites | Symlink `python2` to `python3`, as `Dockerfile.frontdl3` does |
| Scripts expect a deployment layout git does not have | Restructure the repository | Assemble the expected layout in the image build |
| A genuine source-level incompatibility, such as the scipy import or the TabError | Fix it wherever is convenient | Apply a `sed` in the Dockerfile with an inline comment explaining why, keeping the deviation in one auditable place |

Every deviation from the original source belongs in the Dockerfile, numbered and commented.
`Dockerfile.frontdl3` already establishes this pattern with five documented `sed` patches. Follow it.
Deviations scattered through the source tree cannot be audited, and an unaudited deviation
invalidates the reference output.

## Do not fix the bugs

`docs/llm/pitfalls.md` documents places where the code contradicts the published paper: the
screening threshold uses 2×IQR where the paper says 1.5, a 60 percent cloud filter is applied where
the paper says none is, flowline screening is commented out, screening runs 3 iterations where the
paper says 10.

**These are not defects to repair. They are the behaviour being reproduced.** The published dataset
was produced by this code, not by the paper's description of it. Correcting any of them changes the
reference output and destroys its value as a baseline.

If you believe a discrepancy must be addressed, raise it and stop. Do not change it as part of
reproduction work.

The same applies to every published numeric value: thresholds, patch sizes, the 0.5 binarization
cutoff, the 0.1 square kilometre polygon cutoff, learning rates.

## Where the reproduction currently stands

| Requirement | State |
|---|---|
| Segmentation stage in a container | Working. GPU: `Dockerfile.frontdl3` (cu130, built and verified on the user's RTX 5070). CPU: `Dockerfile.frontdl3-cpu`. Both pinned to the same base digest and torch 2.14.0 |
| CPU inference | Available through the `FrontDL3/` submodule fork, which makes `--cuda` optional |
| Scripts stage 3 calls but the root repo lacks | Available. Four from the `FrontDL3/` submodule, and `downloads/enze/Front_DL3/` supplies the rest |
| `build_folder_structure.sh` for stage 2 | In the `FrontDL3/` submodule |
| Scripts missing everywhere | **Resolved (C2c).** Tier B's ~10 "missing" helpers are all in `data_processing/` and only needed `PATH`. Truly absent: `batch_cal_flowline_intersection_num.sh` and the hand-made flowlines (only used by the author's later driver, not by the repo's), and `batch_area_cal.sh` (a broken call in every version, harmless). `intersect.py` is vendored |
| Trained checkpoint, 326 MB | **Obtained**: `downloads/drn54_May5_2022_…tar` (used first). The production logs used `downloads/enze/Front_DL3/drn54_Mar8_2022_…tar`, which is compared at C4. Mount them, do not bake them into an image or commit them |
| Bedrock polygons `bed_GID<n>_??.gmt` | **Not used (decision 2026-10-05).** The published GID278 traces show no truncation, and with no polygon the truncation step passes traces through. The 2026-09-30 plan to derive polygons is dropped |
| `intersect.py`, imported by `truncate_termini.py` | **Vendored** at `vendor/intersect/` (`sukhbinder/intersection` @ `cbf072fc1a`), copied in by `Dockerfile.stage3` with the `np.Inf`→`np.inf` `sed` (deviation 2) |
| Deployment layout | **Built into `Dockerfile.stage3`:** a working root at `/home/staff/enze/Front_DL3` assembled from `batch_inference_termini/`, `FrontDL3/script`, `data_processing/` (on PATH) and the base image's network code. `downloads/enze/Front_DL3/` is only read for reference |
| Reference output for verification | **Available.** `downloads/Termini.zip` holds published traces for all 295 glaciers |
| Source satellite imagery | **GID278 complete:** Sentinel-1 A/D, Sentinel-2, and Landsat-8 (604 scenes, C02/T1) in `GEE/GID278_*` (about 26 GB, gitignored) |
| Stage 2 preprocessing | **Done for GID278, all four sensors** (`Dockerfile.preprocess`, output `tier-c/data/`). The drivers ran unmodified after a seeded `para.ini` (deviation 2). See `IMPLEMENTATION_PLAN.md` C1d |
| Stage 3 (inference → truncation → screening → error) | **Image built and verified** (`Dockerfile.stage3`, CPU and GPU builds). CPU smoke test passed every step. **The full GID278 GPU run is pending on the host.** See Resume here |
| Cutting polygons, flowlines, per-glacier `para.ini` | Only single-glacier samples. A glacier without a cutting polygon is skipped silently |
| Root `Dockerfile` | Empty, zero bytes. The per-stage images are `Dockerfile.gee-download`, `Dockerfile.preprocess`, `Dockerfile.frontdl3(-cpu)` and `Dockerfile.stage3`. `tools/data_viewer/Dockerfile` is the viewer |

### The Zenodo code archive has been checked and adds nothing

`downloads/AutoTerm.zip` is the published code archive, doi:10.5281/zenodo.8270875. It has been
compared against this repository file by file. Findings:

1. It is a GitHub snapshot of this same repository at commit `cab8265`, which is an ancestor of the
   current HEAD.
2. It contains **zero files that this repository does not already have**.
3. It contains **none of the ten scripts the pipeline calls but does not ship**. Do not re-check it
   for them.
4. Exactly one file differs from the working tree, `GEE/batch_download_direct.py`, because a later
   commit rewrote it. See `docs/llm/pitfalls.md` for what changed.

The data products have since been obtained separately and are in `downloads/`. See
`docs/llm/repository-map.md` for the full inventory. They resolved the missing scripts, the
deployment layout, and verification, but **not** the bedrock polygons.

Writing a replacement for a missing script is a last resort. A script you invent is a deviation
from the original, and its output is not reference output.

## Documentation

Detailed documentation lives in `docs/llm/`. Start at `docs/llm/README.md`, which routes by task.

| Read this | For |
|---|---|
| `docs/llm/reproduction-plan.md` | **Phase 1 plan**: tiers, effort, and what actually blocks reproduction |
| `docs/llm/running-and-verifying.md` | The container build, what runs today, how to check a change |
| `docs/llm/repository-map.md` | Which file to edit, the two copies of the network code, missing scripts |
| `docs/llm/pitfalls.md` | Verified traps and every paper-versus-code disagreement |
| `docs/llm/overview.md` | Data flow and the inference chain command by command |
| `docs/llm/conventions.md` | Filenames, `para.ini`, GMT ASCII, projections |
| `docs/llm/components.md` | What a given directory or script does |
| `docs/llm/dependencies.md` | Packages, CLI tools, version constraints |
| `docs/llm/science-context.md` | Why a stage exists, what a number means |
| `docs/llm/refactor-target.md` | The v2 packaging target. Phase 2, not now |

Source documents: `manuscript.md` is the published paper. `AutoTerm Pipeline.docx` is the author's
operating procedure and is the closest thing to a specification for end-to-end setup.

## Two copies of the network code

`pytorch-deeplab-xception/` at the root is the original, GPU-only, unpatched.

`FrontDL3/` is a git submodule pointing at a fork with seven commits that make the code run on
modern Python and on CPU. It also supplies five scripts the root pipeline calls but does not
contain.

Prefer the submodule for anything that has to execute. `docs/llm/repository-map.md` has the full
comparison.

Note the overlap: `Dockerfile.frontdl3` clones upstream and re-applies the same fixes as build-time
`sed` patches. Building from the submodule instead would remove that duplication. That change has
not been made.

## Working rules

1. Verify against the code, not against the paper or the docs. The docs were written by reading the
   code, but the code changes.
2. Do not delete files that look like duplicates or backups. Several carry real divergence and are
   imported by different entry points.
3. Failures here are usually silent. Missing polygons, empty directories, and wrong paths produce
   empty output with exit code 0. Check for output, do not trust the exit code.
4. Never introduce an underscore into a satellite name, glacier ID, or output filename. The pipeline
   parses metadata out of filenames with `cut -d '_'`.
5. State explicitly in your response whenever you change a value that appears in the paper.
6. There is no test suite and no CI. The only real verification is comparing output against a
   previous run.

## Environment

No NVIDIA driver is present in this sandbox, so `--gpus all` will not work here. Use the CPU images
for local verification. The user's host has an **RTX 5070 (sm_120, needs CUDA >= 12.8 torch)**. The sandbox
runs in direct mode, so the repo, `downloads/` and `tier-c/` are the same files on the host.

- Long GPU runs (stage 3 inference) go through `./stage3-host.sh`, **run by the user on the host**. It
  builds `frontdl3` (`Dockerfile.frontdl3`, torch 2.14.0+cu130, needs host driver R580+) and `autoterm-stage3-gpu` (`Dockerfile.stage3
  --build-arg BASE=frontdl3 --build-arg DEVICE=cuda`), checks that the GPU is usable from Docker, runs the
  driver, gives the outputs back to the host user, and checks them. `./stage3-host.sh --cpu` is the same
  path on the CPU image, for testing in the sandbox.
- **All inference images are pinned** (2026-10-05): base `ghcr.io/osgeo/gdal:ubuntu-small-3.13.3@sha256:6425...`
  (Ubuntu 26.04, Python 3.14.4, GDAL 3.13.3), torch 2.14.0, and the other Python packages at fixed
  versions. Never go back to `ubuntu-small-latest`: it is a nightly GDAL dev build, and a build on it
  silently replaced the Tier A-verified image. The pre-pinning image the C3 smoke test ran on is
  archived at `tier-c/images/autoterm-stage3-smoke-2026-10-05.tar` (`docker load -i`).
- Sandbox Docker storage is a 9.7 GB volume. Prune the build cache before building large images.
- The GPU base cannot be built in the sandbox: the CUDA torch wheels pull `pypi.nvidia.com`, which
  the sandbox firewall does not resolve (`sbx policy allow network pypi.nvidia.com` on the host
  would allow it).
- CPU stage 3 throughput here is about 1.1 s per inference patch: about 3.5 min per Landsat-8
  image (198 patches), roughly 75 h for all of GID278. Use the CPU only for smoke tests. Estimated for the
  v1 code on the 5070 from the measured 982 GFLOP per patch: 6–8 h.
