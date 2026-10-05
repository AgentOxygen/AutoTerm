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

Work is tracked step by step in `IMPLEMENTATION_PLAN.md`, Tier C. Read its C1a–C2c entries before
doing anything. The glacier is **GID278 (Jakobshavn)**, and Tiers A and B are done.

**Stage 2 is done for all four sensors (C1d, 2026-10-05).** Landsat-8 was downloaded on the host
(604 scenes in `GEE/GID278_Landsat-8/`). Stage 2 was rerun from scratch into `tier-c/data/`, with
the unmodified drivers after seeding `para.ini` (`Dockerfile.preprocess` deviation 2: the driver
would have taken the Landsat-8 size from a 172x417 edge clip). Every one of the 693 published
GID278 Landsat-8/Sentinel trace dates has a kept stage 2 image. The commands are in the
`Dockerfile.preprocess` header. Logs are in `tier-c/stage2-*.log`.

**Then, in order:**

1. (done) Stage 2. See C1d.
2. **Waiting on the user (2026-10-05), see `IMPLEMENTATION_PLAN.md` "C2, evidence" and "C2c findings":**
   (a) the published GID278 traces show no bedrock truncation, so the recommendation is no bed polygons
   (truncation passes traces through) rather than deriving them; (b) which stage 3 driver to use (the
   repo's, recommended, or the author's working copy); (c) which checkpoint (production logs used
   `Mar8_2022`, not `May5`).
3. (done) C2c. Tier B's "missing" helpers resolve once `data_processing/` is on `PATH`.
4. C3: build the stage 3 image. Copy in `vendor/intersect/intersect.py` with the `np.Inf` sed, and
   choose the cutting polygon (the shrunk ROI or Tier A's hand-drawn `FrontDL3/polygon/cut_polygon.gmt`).
5. C4: compare against the 505 published Sentinel traces and 188 Landsat-8 traces in
   `Termini/GID278`.

**Resolved 2026-10-05:** the resumable-download edit to `GEE/batch_download_direct.py` is now
`Dockerfile.gee-download` deviation 6 (`gee-resume-patch.py`), and the source file is restored. To
rerun a download on the host outside the container, apply deviations 1 and 6 first: the restored
file imports `geetools` and is not resumable.

**Traps found so far, all exiting 0:** stage 3 helpers called by bare name are found only through
`PATH` (`Front_DL3/data_processing`), not through the working directory. stage 2 silently skips glaciers with no Landsat-8. Stage 2
takes the Landsat-8 grid size from whichever scene lists first, which can be a partial edge clip
(deviation 2 in `Dockerfile.preprocess`). A missing `gdal_merge.py` deletes every multi-scene date. Truncation without `intersect.py` crashes
on import for every trace. `Dockerfile.preprocess` now fails its build if any required tool is
missing.

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
2. Truncation needs bedrock polygons that exist in no archive, and **screening silently does
   nothing without truncation output**. A container missing that asset runs clean and produces no
   screened traces. Verify by checking for output files, never by checking exit codes.
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
| Segmentation stage in a container | Working, `Dockerfile.frontdl3` |
| CPU inference | Available through the `FrontDL3/` submodule fork, which makes `--cuda` optional |
| Scripts stage 3 calls but the root repo lacks | Available. Four from the `FrontDL3/` submodule, and `downloads/enze/Front_DL3/` supplies the rest |
| `build_folder_structure.sh` for stage 2 | In the `FrontDL3/` submodule |
| Scripts missing everywhere | **Reopened by Tier B.** The stage 3 run hit about 10 missing helpers on live paths (`batch_cal_complexity.sh`, `remove_duplicate.sh`, and others). See `IMPLEMENTATION_PLAN.md` C2c. `intersect.py` is now vendored (see below) |
| Trained checkpoint, 326 MB | **Obtained**, at `downloads/drn54_May5_2022_0.001_batch16_keep_augmentation.tar`. Verified as a DRN backbone, 1 input channel, 1 output class. Mount it, do not bake it into an image or commit it |
| Bedrock polygons `bed_GID<n>_??.gmt` | **User decision (2026-09-30): derive from `downloads/reference_polygon_new_ID.zip`.** Not done yet. This is a logged deviation. The polygon must be split into one piece per fjord wall, because `truncate_termini.py` skips any polygon that contains both ends of a trace. See `IMPLEMENTATION_PLAN.md` C2 |
| `intersect.py`, imported by `truncate_termini.py` | **Vendored** at `vendor/intersect/`, `sukhbinder/intersection` @ `cbf072fc1a`, the only upstream revision with a matching name and a two-value return. It needs an `np.Inf`→`np.inf` `sed` under NumPy 2 when stage 3 is built |
| Deployment layout | **Solved by example.** `downloads/enze/Front_DL3/` is the author's real working directory. Mount it at `/home/staff/enze/Front_DL3` |
| Reference output for verification | **Available.** `downloads/Termini.zip` holds published traces for all 295 glaciers |
| Source satellite imagery | **GID278 complete:** Sentinel-1 A/D, Sentinel-2, and Landsat-8 (604 scenes, C02/T1) in `GEE/GID278_*` (about 26 GB, gitignored) |
| Stage 2 preprocessing | **Done for GID278, all four sensors** (`Dockerfile.preprocess`, output `tier-c/data/`). The drivers ran unmodified after a seeded `para.ini` (deviation 2). See `IMPLEMENTATION_PLAN.md` C1d |
| Cutting polygons, flowlines, per-glacier `para.ini` | Only single-glacier samples. A glacier without a cutting polygon is skipped silently |
| Root `Dockerfile` | Empty, zero bytes. The per-stage images are `Dockerfile.gee-download`, `Dockerfile.preprocess`, `Dockerfile.frontdl3-cpu` |

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

No NVIDIA driver is present in this sandbox, so `--gpus all` will not work. Use the submodule's CPU
inference path for local verification.
