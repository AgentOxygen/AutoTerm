# Phase 1 implementation plan — reproduce one end-to-end AutoTerm run

Temporary task list for agentic development. Not part of `docs/llm/`, which is the durable
documentation — this file tracks execution and should be deleted once Tier C produces a verified
end-to-end trace for at least one glacier. Source of truth for the *why* behind each tier is
`docs/llm/reproduction-plan.md`; this file only turns it into checkable steps.

Ground rules carried over from `CLAUDE.md`, restated because they govern every task below:

- **Do not edit source to make it run.** Fix the environment (mounts, symlinks, Dockerfile `sed`
  patches with a numbered comment). Any unavoidable source deviation gets logged in the Dockerfile,
  not silently patched in place.
- **Do not fix the four documented bugs** (2×IQR vs 1.5, 60% cloud filter, flowline screening
  disabled, 3 vs 10 screening iterations). Reproducing them is the point.
- **Verify by output, not exit code.** Every task below ends with a concrete file-existence or
  numeric check, not "the script ran."
- **This sandbox has no NVIDIA driver.** `Dockerfile.frontdl3` as written needs `--gpus all` and a
  CUDA torch wheel — it cannot run here. Everything below uses the `FrontDL3/` submodule's CPU path
  (`--cuda` optional) for local execution. GPU-only validation of the exact `Dockerfile.frontdl3`
  image is out of scope for this sandbox and stays a later, separate check on GPU hardware.
- **Escalate to Opus when complexity is high or confidence is low.** Before implementing a task
  whose blast radius is hard to bound up front — a Dockerfile/environment change, a path-mounting
  decision that affects multiple downstream scripts, resolving a silent-failure mode, or the bedrock
  polygon derivation in Tier C — or after hitting a result that doesn't match the expected baseline
  and the cause isn't obvious, spawn an Opus review (`Agent` with `model: "opus"`) rather than
  pushing forward on Sonnet alone. Give it the specific file(s), the expected vs. actual output, and
  the constraint set above (minimal-modification rule, do-not-fix-bugs rule) so it reviews within
  the same guardrails. Routine, well-scoped steps (running a script, checking a file exists) don't
  need this — reserve it for judgment calls and verification of anything non-obvious.

---

## Tier A — confirm segmentation runs here, on CPU

Goal: reproduce the "28 patches → one 814-point Jakobshavn trace" result without a GPU, so the
checkpoint and environment are validated before building on top of them.

- [x] A1. Built `Dockerfile.frontdl3-cpu` at the repo root: `COPY`s the `FrontDL3/` submodule
      (rather than cloning upstream, since the submodule already carries the CPU-support and py3
      commits) onto the same `ghcr.io/osgeo/gdal` base as `Dockerfile.frontdl3`, with CPU-only
      `torch`/`torchvision` from `download.pytorch.org/whl/cpu`. Two build-time `sed` patches
      logged in the file: (1) `exe_inference.sh` hardcodes `--cuda` even though the submodule's
      `inference.py` made it optional — stripped at build time; (2) the checkpoint's tensors were
      saved from a CUDA device, so `torch.load` needs `map_location=torch.device('cpu')` on
      inference.py:78, patched the same way.
      Sandbox note: the build needed two outbound domains the default-deny network policy blocked —
      `download.pytorch.org` (the index) and `download-r2.pytorch.org` (the actual wheel CDN it
      redirects to). Both required `sbx policy allow network <domain>` on the host before the build
      could complete; this is sandbox network config, not a source or Dockerfile deviation.
- [x] A2. Checkpoint mounted read-only at `/Front_DL3/network.tar`, not baked into the image.
- [x] A3. Ran `preparing_influence.sh /Front_DL3/train` + `exe_inference.sh
      /Front_DL3/polygon/cut_polygon.gmt network.tar` against the submodule's own sample image and
      cutting polygon.
- [x] A4. **Confirmed: 28 patches, one terminus trace of exactly 814 points for Jakobshavn Isbrae**
      — matches the GPU baseline recorded in `Dockerfile.frontdl3`'s header comment exactly, no
      drift. Output at `out/in_polygon_gmt/` (gitignored, local run artifact — see run command in
      `Dockerfile.frontdl3-cpu`'s header comment to reproduce).

## Tier B — stage 3 driver dry run against the author's directory

Goal: exercise the full `batch_inference_termini/` driver end to end on sample data, with the
correct layout mounted, and get an explicit (not silent) confirmation that truncation/screening
no-op without bedrock polygons.

- [x] B1 (revised). Did **not** bind-mount `downloads/enze/Front_DL3` directly, read-only or
      otherwise: the scripts write scratch output (`test_output/`, `post_output/`, `list/`, etc.)
      straight into `working_root`, so a read-only mount can't run them and a read-write mount would
      mutate the user's 12 GB external download in place — unacceptable. Instead copied only the
      code/config (`para.ini`, every `batch_*.sh`, `script/`, `data_processing/`,
      `pytorch-deeplab-xception/`, `quantification_error_analysis/`, ~2.6 MB total) into
      `tier-b/working-root/` (gitignored), skipping `post_output/` (4.3 GB byproducts), `train/`,
      `polygon/`, and every checkpoint `.tar`. The original `downloads/enze/Front_DL3/` was only ever
      read from (`cp`), never mounted — confirmed untouched. `tier-b/working-root/` is mounted
      read-write at `/home/staff/enze/Front_DL3`, satisfying the same 59/76 path references without
      editing any script and without risk to the source download.
      Two CPU patches applied to this local copy only (same two deviations as Tier A, mirrored onto
      this copy's own `exe_inference.sh`/`inference.py`, which differ enough from the submodule's
      that the Tier A patches don't directly apply): strip the hardcoded `--cuda` from
      `exe_inference.sh`'s live `python -u .../inference.py` call, and guard the per-batch
      `x.cuda()` call in `inference.py` behind `if args.cuda` (this copy predates the submodule's
      commit 6ec56ca and never had that guard at all) plus `map_location='cpu'` on `torch.load`.
- [x] B2 (revised). Assembled a minimal sample-glacier tree at `tier-b/sample-data/GID278/` (GID278
      = Jakobshavn/Sermeq Kujalleq, confirmed against `Glacier Identification.csv`'s coordinates)
      rather than the ice mask subtree, since nothing in `batch_inference.sh` through
      `batch_smoothness_truncate.sh` reads it. Reused Tier A's validated polygon and sample image,
      renamed to the `<date>_<Satellite>_<GID>_stretch` convention from `docs/llm/conventions.md`.
      This is a constructed test fixture, not source, and is gitignored under `tier-b/`.
- [x] B3 (revised, important finding). `batch_inference_plot_mv_figure_dir.sh` **as found in the
      author's real directory has its `bash batch_inference.sh ...` call commented out**
      (`downloads/enze/Front_DL3/batch_inference_plot_mv_figure_dir.sh:27`) — the root repo's copy
      at `batch_inference_termini/batch_inference_plot_mv_figure_dir.sh` has the same line live. The
      author's driver only does post-processing; inference is a separate step in their real
      workflow (consistent with `post_output/`'s 4.3 GB of leftover rasters in that directory). This
      contradicts nothing in `docs/llm/`, it's simply undocumented — worth a `repository-map.md`
      note. Reproduced correctly by running `batch_inference.sh` first (as Tier A already validated
      standalone), then the driver for everything downstream — not by uncommenting the author's
      script.
- [x] B4. Checked explicitly at each boundary:
      - [x] **Inference**: confirmed — same 814-point Jakobshavn trace as Tier A, now under the
        real deployment layout (`GID_278_Landsat-8/in_polygon_gmt/network/...gmt`).
      - [x] **Truncation**: `truncate_termini/network/` exists but holds **zero `.gmt` files** —
        confirmed empty, but not for the reason `pitfalls.md` describes. The real, observed cause:
        `data_processing/truncate_termini.py` crashes on import —
        `ModuleNotFoundError: No module named 'intersect'` — for every trace, so nothing is ever
        written. **`intersect.py` (the module providing `intersection(x1,y1,x2,y2)`) is missing from
        every source checked: root repo, `FrontDL3/` submodule, `downloads/enze/Front_DL3/`, and
        `downloads/AutoTerm.zip`.** This is a real gap not listed anywhere in
        `repository-map.md`'s missing-scripts table, and it blocks truncation independently of the
        bedrock polygons — even with polygons in hand, truncation cannot run without this module.
      - [x] **Screening**: runs (the `truncate_termini/$temp` directory does exist, so
        `batch_smoothness_truncate.sh` doesn't skip outright), but trivially no-ops over the empty
        set — 0 traces to abandon each iteration, "move on" every time. Screening also hit its own
        missing dependency: `batch_cal_complexity.sh` (called from `batch_smoothness_truncate.sh`)
        is not present in the root repo, the submodule, or `downloads/enze/Front_DL3/`.
      - [x] **Beyond B's scope, observed anyway**: the run continued through every remaining stage
        (`merge`, `area_cal`, `split_data_by_name`, `calculate_offset_sentinel`,
        `calculate_error`, `plot_time_series`, `mv_abandon_duplicate`) and surfaced roughly ten more
        missing helper scripts (`batch_plot_result.sh`, `batch_cal_flowline_intersection_num.sh`,
        `batch_abandon_on_intersection.sh`, `batch_cal_termini_length.sh`, `remove_duplicate.sh`,
        `merge_two_calving2.sh` at its expected call-site path, `calculate_area2.sh`,
        `split_data_by_name.sh`, `plot_time_series.sh`) plus several `IndexError`s from computing
        percentiles over empty arrays (expected — only one date of imagery here). None of this
        blocks Tier B's own goal, but it means `repository-map.md`'s "every script on a live code
        path is now available" claim needs revisiting before Tier C is scoped — recommend a
        dedicated pass before starting Tier C rather than assuming that count is still accurate.
      - Overall exit code: 0 throughout, confirming the project's core verification-discipline point
        — every one of these failures was silent at the exit-code level.
- [x] B5. This checklist entry **is** the run log — see the findings above. Raw run output kept
      locally at `tier-b/` (gitignored), not committed.

## Tier C — real imagery, truncation, and screening (the tier that matters)

- [x] **C0a. Bedrock polygon source — decided by the user (2026-09-30): derive them from
      `downloads/reference_polygon_new_ID.zip`.** Not contacting the authors. The consequence
      is that truncation runs on derived polygons, which is a logged deviation (see C2).
- [x] **C0b. GEE access — resolved.** The download ran successfully from the host-side venv
      `.env/` (earthengine-api, Python 3.14), not from the `Dockerfile.gee-download` container.
      `GEE/gee-downloads/` still holds only the glacier list.

- [x] C1a. **Download done for GID278 (Jakobshavn), Sentinel only.** Output is written flat into
      `GEE/` (gitignored imagery, about 25 GB total). Every file has a valid TIFF header:

      | Folder | Files | Band | Date range | Published `Termini/GID278` traces |
      |---|---|---|---|---|
      | `GEE/GID278_Sentinel-1_D` | 859 | HH | 2014-10-19 → 2023-06-29 | Sentinel1: 250, both passes (2014-10 → 2022-02) |
      | `GEE/GID278_Sentinel-1_A` | 807 | HH | 2014-10-11 → 2023-06-26 | |
      | `GEE/GID278_Sentinel-2`   | 523 | B4 | 2015-07-10 → 2023-06-28 | Sentinel2: 255 (2015-07 → 2021-10) |

      - Sensor choice: the script's active blocks are the original's (S1-D, S1-A, S2). The Landsat
        blocks are commented out upstream, so **no Landsat imagery was downloaded**. C4 can
        therefore compare only against the 505 Sentinel traces, not the 477 Landsat 5/7/8
        traces in the published GID278 set.
      - Sentinel-2 has about twice as many files as published traces because many scenes appear
        twice (original and reprocessed product IDs, e.g. `20150710T153226_20150710T153237` vs
        `20150710T153226_20160809T105246`). Expect screening and duplicate removal to account
        for this, and check that it does at C4.
      - Two Sentinel-2 files from 2016-03-26 are about 2 KB each, probably empty clips. Stage 2's
        `batch_remove_partial_images.sh` should drop them. Confirm that it does.
      - **Resolved 2026-10-05: the source file is restored, and the edit is now `Dockerfile.gee-download`
        deviation 6 (`gee-resume-patch.py`, whose output is byte-identical to the edited file).** Original note:
        `GEE/batch_download_direct.py` was
        edited in place (Sep 30) to make interrupted downloads resumable. It skips existing
        `.tif` files and iterates `aggregate_array('system:index')` instead of
        `toList().get(i)`. The added `.select('HH')` / `.select(sel_bands)` repeat the collections'
        own `.select`, so the selected images should be unchanged. However, this breaks the
        minimal-modification rule: the change is not in the Dockerfile, and
        `Dockerfile.gee-download` `COPY`s the edited file without mentioning it. Before C4, either
        restore the committed file with `git checkout GEE/batch_download_direct.py` and move the
        resume logic into a numbered deviation in `Dockerfile.gee-download`, or at minimum
        document it there. It affects only which files get fetched, not pixel content.
- [x] C1b. **(Superseded by C1d: this Sentinel-only output was deleted 2026-10-05.)** **Stage 2 preprocessing: process, stretch, partial-removal, and cutting polygon done
      for GID278 (2026-09-30). Upsample and `para_upsample.ini` are blocked on Landsat-8 (C1c).**
      - Environment: `Dockerfile.preprocess` (image `autoterm-preprocess`) on **ubuntu:18.04**. It is
        the only checked base that still packages `gdal_contrast_stretch` (dans-gdal-scripts),
        which `batch_stretch.sh` calls. Focal, jammy, and the osgeo/gdal image lack it. GDAL 2.2.3 /
        Python 3.6. `preprocess-entrypoint.sh` assembles the author's data-directory layout
        (AutoTerm Pipeline.docx Step 3) under the mount
        `tier-c/data` → `/home/staff/enze/data1/Greenland_front_Mapping/data`. It creates
        `GID278/GID_278_<sat>/original_image/`, and the file entries are symlinks into the
        read-only `GEE/` mount, so the downloads are never written. It then runs the author's
        `build_folder_structure.sh`. Note: GEE writes `GID278_<sat>` but every stage 2 script
        reads `GID_278_<sat>`. The procedure leaves that rename implicit.
      - **`batch_stretch.sh` copy:** the procedure puts `Front_DL3/data_processing` on PATH, so the
        one that runs is `data_processing/batch_stretch.sh` (`-histeq 100`, byte-identical to the
        author's), not `pre-processing/batch_stretch.sh` (`-histeq 20`).
      - **Deviation 1 (logged in `Dockerfile.preprocess`):** `batch_read_box_process.sh`, run
        unmodified, **exits 0 having processed nothing** for a Sentinel-only glacier. It
        `continue`s at its Landsat-8 `original_image` check and leaves a *partial* `para.ini` (GID and
        ROI only). That file is a trap: a rerun sees `para.ini`, skips the gate, and calls
        `batch_process.sh` with empty size args. Instead, `preprocess-sentinel.sh` writes `para.ini`
        with the driver's own lines and helpers, minus the Landsat sizes, and runs
        `batch_process_sentinel.sh`. That is `batch_process.sh` with its Landsat-8 lines removed by
        `grep -v` at build time, the Sentinel lines byte-identical. It then runs
        `batch_remove_partial_images.sh` unchanged.
        `para.ini`: ROI −49.83 69.105 −49.47 69.27, `x_size_S=1469 y_size_S=1872` (first Sentinel-2
        original, 10 m).
      - **Silent failure caught and fixed:** the first run's image lacked `gdal_merge.py` (bionic ships
        it in `python-gdal`, not `python3-gdal`). Every same-date merge failed with "command not
        found", the script deleted the parts anyway, and 46 of 471 Sentinel-2 dates vanished
        with exit 0. Now fixed, and the image build fails if any tool a stage 2 script calls
        is missing. The output was wiped and regenerated.
      - **Verified output** (`tier-c/data/GID278/`, gitignored, log `tier-c/stage2a.log`):

        | Sensor | GEE files | Unique dates | `after_merge/` | `hist_eq/` kept | Abandoned (>10% zero px) |
        |---|---|---|---|---|---|
        | Sentinel-2   | 523 | 471 | 471 | 470 | 1 |
        | Sentinel-1_D | 859 | 780 | 780 | 700 | 80 |
        | Sentinel-1_A | 807 | 437 | 437 | 432 | 5 |

        `after_merge` equals the unique-date count for all three sensors. The 501 log lines
        `rm: cannot remove 'temp.tif'` equal exactly the number of merges (52 + 79 + 370), so they
        are harmless noise from the original script's merge branch. The output is
        `<date>_Sentinel2_GID278_stretch.tif` / `<date>_Sentinel1_GID278_{D,A}_stretch.tif`,
        Byte, 1469×1872, histogram-equalized (mean ≈ 128.8). The two 2 KB Sentinel-2 files from
        2016-03-26 were granule-edge slivers. They merged into a complete image with that date's
        two full scenes, so nothing was lost.
      - `batch_generate_truncating_polygon.sh` ran unmodified and produced
        `GID278/polygon/GID_278_cutting_polygon_shrink.{gmt,kml,shp}`, the ROI shrunk 10% per side
        (checked by hand). The author notes this shrunk box is sometimes unsuitable. Tier A's
        `FrontDL3/polygon/cut_polygon.gmt` is a hand-drawn 31-vertex Jakobshavn polygon. Which
        of the two stage 3 is fed is a C3 decision (`batch_inference.sh` takes the polygon as
        `$2`). Record whichever is used.
- [x] **C1c. Landsat-8: user chose option (a), download it (2026-09-30).** Downloaded on the host
      2026-10-05: 604 scenes in `GEE/GID278_Landsat-8/`. See C1d for the evaluation and stage 2 rerun.
      - **Checked on GEE on 2026-09-30:** `LANDSAT/LC08/C01/T1` → "asset not found", so Collection 1
        is gone. `LANDSAT/LC08/C02/T1` has 747 scenes over the GID278 ROI in the script's window,
        604 of them with `CLOUD_COVER < 60`. B8 is uint16 at 15 m, and the `system:index` format
        `LC08_PPPRRR_YYYYMMDD` is the same one `batch_process_Landsat-8_images.sh` parses (`cut -d
        '_' -f 3`).
      - `Dockerfile.gee-download` deviations 2-5 (transform in `gee-landsat8-patch.py`) build
        `batch_download_landsat8.py`, selected with `-e GEE_SCRIPT=batch_download_landsat8.py`:
        (2) uncomment the Landsat-8 block, (3) C01 → C02, (4) drop the Sentinel blocks so the
        consumed S1/S2 inputs can't change, (5) restore the loop's `readline()`.
      - **New finding:** the committed HEAD `batch_download_direct.py` never finishes. The f1df8ca
        rewrite dropped the `line = f.readline()` that the Zenodo snapshot cab8265 had at the end
        of the loop, so it keeps re-running the first glacier. The Sentinel run must have been
        stopped by hand, and the resume edit made the repeats harmless.
      - **Sandbox auth finding:** the sandbox's `~/.config/earthengine/credentials` fails token
        refresh with `invalid_scope` when earthengine-api sends the stored read-only scopes. It
        works with the scopes left out, which is how the read-only query above ran. The container
        recipe in the Dockerfile header was also wrong (`HOME=/root` is not traversable by a
        non-root uid) and has been corrected. Run the download on the host, where it worked for
        S1/S2.
      - **After the download: delete `tier-c/data` and rerun stage 2 from scratch with the
        unmodified author drivers** (`batch_read_box_process.sh` → `batch_remove_partial_images.sh` →
        `batch_upsample.sh` → `batch_generate_para_upsample.sh` →
        `batch_generate_truncating_polygon.sh`, the order in `batch_preprocess_images/haha.sh`).
        With Landsat-8 present, the gate passes, so **deviation 1 and `preprocess-sentinel.sh`
        are no longer needed for GID278**. Do not rerun on top of the current `tier-c/data`:
        the existing Sentinel-only `para.ini` makes the driver read `x_size_L` as missing and
        pass bad args. Verify by per-sensor file counts as in C1b. Landsat-8 `after_merge/` should
        equal the number of unique Landsat dates.
      - Background on the gating, unchanged: the two remaining stage 2 steps require Landsat-8. `batch_upsample.sh` branches on `x_size_L` (upsample only if < 1000), and
      `batch_generate_para_upsample.sh` `continue`s without writing `para_upsample.ini` if
      `GID_<n>_Landsat-8/upsample` is empty. For GID278's Sentinel data the practical effect is small:
      `factor_S = 1000/1469 + 1 = 1`, so the "upsample" is a same-size cubic `gdalwarp` copy.
      However, `para_upsample.ini` is what stage 3 reads. The options are:
      (a) Download Landsat-8 by enabling the script's LC08 block. The committed block targets
          `LANDSAT/LC08/C01/T1`. Collection 1 is believed decommissioned on GEE, which is unverified
          here because the sandbox has no working EE auth for containers. If so, the substitute
          `LANDSAT/LC08/C02/T1` is a logged deviation. This also adds up to 188 published Landsat-8
          traces to compare against at C4.
      (b) Stay Sentinel-only and extend deviation 1 to upsample/para_upsample. This needs a
          stand-in for `x_size_L`, which is an invented number, so (a) is preferred.
- [x] **C1d. Landsat-8 evaluated and stage 2 rerun from scratch, all four sensors (2026-10-05).**
      - **Download:** 604 `.B8.tif`, all readable, UInt16, 15 m, nodata 0, EPSG:32622 (92 of them
        in 32623). 482 unique dates (2013-03-19 → 2023-06-28). 118 dates have 2–3 scenes. One
        `LO08_` (OLI-only) file parses fine. **All 188 published Landsat8 dates are covered.**
      - **Midnight-sun passes:** 81 scenes from paths 081–084, rows 232/233, dim (median DN about
        7.7k against 19.3k by day). 10 published traces come from dates that have only these scenes,
        so the author's download had them too. Kept. On 20 dates they share a date with a day scene,
        and `ls` order merges them *over* the day scene (`gdal_merge -n 0`, later wins). 7 of those
        dates have published traces. That is original behaviour; watch those dates at C4.
      - **Trap, logged as `Dockerfile.preprocess` deviation 2 (user-approved):**
        `batch_read_box_process.sh` takes `x_size_L/y_size_L` from `find | head -n 1`, which is
        `LC08_007012_20130429.B8.tif`, a 172x417 edge clip. Evidence for the author's real value:
        the median vertex spacing of the published traces is Landsat8 8.1 m and Sentinel 10.8 m. A
        980x1248 grid upsampled 2x predicts 8.1 m, and 172x417 (upsampled 6x) predicts 15.3 m.
        1469x1872 predicts 10.8 m for Sentinel, which validates the method. A 1043x1296
        "first full scene" (path 008/011, factor 1) predicts 15.2 m, so the rule is the *most
        common* size (980x1248, 261 of 604), not the first full one. `preprocess-seed-para.sh` writes
        `para.ini` with the driver's own lines using that size. The drivers then ran unmodified.
      - **Verified output** (`tier-c/data/GID278/`, logs `tier-c/stage2-{0..5}-*.log`, 19 min):

        | Sensor | Unique dates | `after_merge/` | `hist_eq/` kept | Abandoned | `upsample/` size |
        |---|---|---|---|---|---|
        | Landsat-8    | 482 | 482 | 353 | 129 | 1960x2496 (factor 2) |
        | Sentinel-2   | 471 | 471 | 470 | 1   | 1469x1872 (factor 1, cubic copy) |
        | Sentinel-1_D | 780 | 780 | 700 | 80  | 1469x1872 |
        | Sentinel-1_A | 437 | 437 | 432 | 5   | 1469x1872 |

        Sentinel counts are identical to the C1b run. There were 623 merges (501 Sentinel and
        122 Landsat). The only log noise is the 501 known `rm: cannot remove 'temp.tif'` lines and
        one expected `rm` of a missing `para_upsample.ini`. `para_upsample.ini` has
        `x_size_L=1960 y_size_L=2496 x_size_S=1469 y_size_S=1872`. The cutting polygon
        `polygon/GID_278_cutting_polygon_shrink.*` was regenerated.
      - **Published-date survival:** every published date has a kept `hist_eq/` image (Landsat8
        188/188, Sentinel2 255/255, Sentinel1 250/250). None was lost to partial-image removal.
      - Old Sentinel-only logs: `tier-c/old-sentinel-only/`.
- [ ] **C2, evidence found 2026-10-05, awaiting the user's decision: the published GID278 traces show no
      bedrock truncation.** All 693 Landsat8/Sentinel traces run the full ice margin: along the north
      wall, around the terminus, and back along the south wall. Both ends stop on the
      `GID_278_cutting_polygon_shrink` box, mostly its west edge at −49.794. 90% of endpoints are within
      32 m of the box edge (p50 13 m); the farthest few are still at −49.79, and the single outlier is
      L8 2014-06-24 (458 m, near the east edge). A fjord-wall cut would leave endpoints near the
      terminus (about −49.65 to −49.70). Plot: `tier-c/c2-published-traces-GID278.png` (gitignored).
      `truncate_termini.py` with no `bed_GID278_??.gmt` files at all: `ls` matches nothing,
      `get_intersect` returns `(0, len)`, and the whole trace is written out (pass-through), provided
      `intersect.py` imports. Tier B's empty `truncate_termini/` was the import crash, not the missing
      polygons. **Consequence:** derived wall polygons would cut lateral margins that the published
      traces keep. Not providing any bed polygon reproduces the published behaviour with no deviation.
      The same evidence confirms that the author's cutting polygon for GID278 was the shrunk ROI, which is
      also what `log_Jun13.txt` (MC dropout on GID278) shows.
- [ ] C2. Derive `bed_GID278_??.gmt` from `reference_polygon_new_ID/GID278.gmt`, placed where
      `bed_path=/home/staff/enze/data1/ice_mask/GIMP/crop_bed/buffer_15` resolves (mount, no
      script edits). **This is a deliberate deviation.** Log it as a numbered, commented step in
      the build or run script, and flag in any results write-up that GID278 truncation used
      derived polygons, so those traces are not strictly reference output.
      - What the archive holds: 289 per-glacier reference polygons (`GID<n>.{gmt,shp,kml,...}`),
        plus four `GID<n>_Landsat-<n>.*` variants, three `.gmt-e` sed backups, `figure/GID<n>.jpg`
        previews, `reference_polygon.pptx`, and `script/combine_glacier_front.py` (the paper
        §3.2 label-generation script, which joins a trace to the reference polygon at its
        nearest points). `GID278.gmt` is one closed ring of 192 lon/lat vertices with no `>`
        segment headers.
      - **Semantic caveat:** per paper §3.2 (Fig. 2) a reference polygon is a *label-generation*
        artifact: the glacier outline with a terminus drawn up-glacier of every TermPicks trace.
        It is not the GrIMP bedrock mask buffered by 15 (the `buffer_15` the original path
        names). Its fjord-wall edges are the part that plays the bedrock role.
      - **Mechanical constraint, verified in `data_processing/truncate_termini.py`:** for each
        `bed_*` file, the script finds which trace points lie inside that polygon and
        `continue`s (skips the polygon) when the median inside-index is within `len/10` of the
        trace midpoint. It then cuts the trace at the intersection nearest the midpoint, on
        whichever side the inside points fall. The reference polygon contains **both** ends of
        every trace by construction (§3.2), so passed as a single `bed_GID278_01.gmt` it is
        skipped for every trace and truncation silently does nothing. The derivation must
        therefore produce **one polygon per fjord side** (`bed_GID278_01.gmt`,
        `bed_GID278_02.gmt`, a two-character suffix to match `??`), each containing only one end
        of a typical trace. For example, split the ring at its terminus segment and close each
        wall side into its own polygon, or intersect it with left/right halves of the ROI.
        Choose the method deliberately, record it, and check it against `figure/GID278.jpg`.
      - `truncate_termini.py` also needs a module `intersect` that exists nowhere (see C2b).
- [x] **C2b. `intersect.py` vendored (user-approved 2026-09-30)** at `vendor/intersect/`, verbatim
      from `sukhbinder/intersection` at commit **`cbf072fc1a`** (2020-04-04), with its MIT LICENSE.
      Provenance and sha256 are in `vendor/intersect/README.md`. **Pin reasoning:** it is the only
      upstream revision that is both named `intersect.py` and returns two values. Revisions from
      `50bbb4e64d` (2020-12) onward, and every PyPI release, return `(x, y, i, j)`, and
      `truncate_termini.py`'s `lo, la = intersection(...)` would raise on those. The first
      vendoring attempt used `50bbb4e64d`, and a unpack test caught it.
      - Still to do when the stage 3 image is built (C3): `COPY` it next to `truncate_termini.py`,
        and apply `sed 's/np\.Inf\b/np.inf/'` (line 90, NumPy ≥ 2 removed `np.Inf`, the same
        change as upstream's own `bb1348ba14`). Log both as numbered deviations. Verified on
        NumPy 2.3.5 with that `sed`: correct intersections, and the two-value unpack works.
- [x] C2c. **(Done 2026-10-05; see "C2c findings" below.)** **Re-audit the missing screening and downstream helpers from Tier B** (B4 list:
      `batch_cal_complexity.sh`, `batch_plot_result.sh`, `batch_cal_flowline_intersection_num.sh`,
      `batch_abandon_on_intersection.sh`, `batch_cal_termini_length.sh`, `remove_duplicate.sh`,
      `merge_two_calving2.sh` at its call-site path, `calculate_area2.sh`, `split_data_by_name.sh`,
      `plot_time_series.sh`). For each, decide whether the call site is on the live path for
      screening, duplicate removal, the S1 offset, and error. Fix `repository-map.md`'s claim that
      "every script on a live code path is available". Bring decisions to the user before
      inventing any replacement.
- [x] **C2c findings (2026-10-05), with decisions pending for the user:**
      - **Tier B's "missing everywhere" helper list was wrong.** All the helpers except one exist in the
        repo's own `data_processing/` (byte-identical to the author's, except plot labels in
        `plot_hist.py` / `plot_time_series.sh`). The step scripts call them by bare name
        (`bash batch_cal_complexity.sh`), and bash then searches `PATH`. The author's procedure (AutoTerm
        Pipeline.docx, Step 3) puts `Front_DL3/data_processing` on `PATH`; Tier B didn't. The stage 3
        image must do the same, as `Dockerfile.preprocess` already does.
      - **Two driver versions.** The repo's `batch_inference_termini/batch_inference_plot_mv_figure_dir.sh`
        (3 length/smoothness iterations, no flowline steps), and the author's working copy
        `downloads/enze/Front_DL3/` (2 iterations, plus `batch_cal_flowline_intersection_num.sh` →
        `batch_abandon_on_intersection.sh`, and inference commented out). The author's production logs
        from March 2023 (`log_Mar2{3,4,5,8}_2023*.txt`; `Termini.zip` is dated 2023-03-29) all ran **3**
        iterations, so the working copy's `{1..2}` is a later edit. The flowline-intersection steps
        appear from 2023-03-24 onward (absent on 03-23). They need `batch_cal_flowline_intersection_num.sh`
        (in no archive; the logs show it calls `calculate_flowline_intersection_num.sh <dir>
        data1/flowline/manual/GID<n>_upsample.gmt`) **and** hand-made flowlines (in no archive). Without
        them, `batch_abandon_on_intersection.sh` prints "no number of intersection" and abandons nothing.
        No log records a GID278 driver run, so whether GID278 went through that screening is unknown.
      - Step scripts present in both copies differ only in `ls | grep "GID"` vs `grep "-"`, which select
        the same sensor directories here, and in the repo's `batch_inference.sh` hist_eq fallback. The
        repo-only step scripts (`batch_remove_duplicate`, `batch_merge`, `batch_area_cal2`,
        `batch_split_data_by_name`, `batch_plot_time_series`) appear in the March 2023 logs, so they
        are the ones that ran.
      - `batch_area_cal.sh` (called once after the area loop in both drivers) exists only as
        `quantification_error_analysis/batch_area_cal.sh`, which has different arguments and `/home/zez`
        paths. It never appears in the production logs, and the next step reads `batch_area_cal2.sh`'s
        output. Missing → harmless no-op, the same as in production.
      - **Checkpoint question (new):** every March 2023 production run used
        `drn54_Mar8_2022_0.001_batch16_keep_augmentation.tar` (in `downloads/enze/Front_DL3/`, same size
        as May5). `May5` appears only in the Sep/Oct 2023 logs, after publication. The paper says the
        chosen learning rate was 2e-3; both of those are 1e-3, and the only drn54 2e-3 checkpoint
        is `drn54_Apr13_2022_0.002`. Unresolved, raise at C3/C4.
- [ ] **C3, stage 3 image built and smoke-tested on CPU (2026-10-05). The full run is for the host GPU.**
      - `Dockerfile.stage3` (decisions: the repo's driver, no bed polygons, shrunk cutting polygon,
        `May5` first). The CPU build is `autoterm-stage3` (on `frontdl3-cpu`). The GPU build is
        `--build-arg BASE=frontdl3 --build-arg DEVICE=cuda` (on `Dockerfile.frontdl3`, torch 2.14.0+cu130). That
        build can't run in the sandbox: `pypi.nvidia.com` is not resolvable. `stage3-host.sh` builds
        either one, runs a GPU preflight, runs the driver, chowns the outputs and checks them.
      - **New trap, fixed in the image:** the CPU base lacked `bc`, which every screening abandonment test
        pipes through. Without it, nothing would have been screened out, with exit 0. The build now fails
        if `bc`, `gs`, GMT, the GDAL scripts or any `data_processing` helper is missing.
      - **Smoke test** (`tier-c/smoke/`, gitignored): 6 images per sensor, all on dates with published traces,
        64 min on 24 CPU cores. Every driver step ran. 24 images → 24 `in_polygon_gmt` traces →
        24 truncated traces, **all identical to their inputs** (the pass-through, as decided) → 6
        screened out (5 S1-A, 1 S1-D: with 6 samples the IQR window borrowed from S2 is very narrow) →
        18 final traces. Points per trace L8 2,020–3,710 and S1/S2 1,562–2,748 (published medians
        2,925 / ~2,150). Against the published trace for the same date, the median point distance is
        36 m (median of per-trace means 105 m). These are raw, pre-offset traces from `May5`; not the C4 metric.
      - Log noise, all expected or plot-only: 24 × `ls ... bed_GID278_??.gmt` (no bed polygons, by
        design); `rm` of scratch dirs absent on a first run; `mv: cannot stat` when a trace already
        moved by the smoothness test also fails the length test; one `find_min_max.py` IndexError
        in `plot_time_series.sh` (the `accu/GID278_all.txt` it plots doesn't exist, so it affects a figure only).
      - **Throughput:** 1.06 s per 960x720 patch on CPU; 198 patches per L8 image, 112 per Sentinel image;
        GID278 is about 249k patches (245 PFLOP at 982 GFLOP per patch, measured with FlopCounterMode).
        CPU about 73 h. **5070 with the v1 code: estimated 6–8 h** (batch 1, FP32, no `no_grad`, per-patch
        GeoTIFF writes). Measure it on the first host run.
      - **Pinned stack + host script verified (2026-10-05).** The inference images moved from the nightly
        `ubuntu-small-latest` (GDAL 3.14.0dev, rebuilt daily) to `ubuntu-small-3.13.3@sha256:6425...`
        with torch 2.14.0 and pinned Python packages. The GPU image is `cu130` (same torch; host driver
        R580+). `./stage3-host.sh --cpu` on 2 images per sensor (`tier-c/smoke-script/`): built,
        ran in 21 min, chowned outputs to uid 1000, and reported 8 traces → 7 final, with only the known
        figure-only Traceback. **All 8 traces are bit-identical** to the smoke run on the old
        stack, so CPU inference is deterministic and pinning changed no output.
- [ ] C3. Run `batch_truncate_termini.sh` and the screening scripts
      (`batch_smoothness_truncate.sh` and downstream) against C1's imagery and C2's polygons.
      Confirm `truncate_termini/` is now non-empty and screening actually executes (not skipped).
- [ ] C4. Compare output against `Termini/GID<n>.shp` (from `downloads/Termini.zip`) on `Date` and
      `Satellite`, using `data_processing/calculate_error.py`'s enclosed-area/length metric. Compare
      against the paper's published figures: 79 m test error before screening, 62 m after, 37 m
      average duplicate-trace uncertainty. A result far outside that range is a signal to
      investigate, not to adjust a threshold — see "do not fix the bugs" above.

## Tier D — MC dropout, merge, figures (after C succeeds)

- [ ] D1. Run `MC_dropout/batch_MC_dropout.sh`, sourcing `batch_plot_truncate_MC_dropout.sh` from
      `downloads/enze/Front_DL3/` (the one script this repo and the submodule both lack).
- [ ] D2. Run the merge stage (`merge_shp/`) using `downloads/uncertainty_all.csv`.
- [ ] D3. Confirm final shapefile output structurally matches `Termini.zip`'s format for the same
      glacier (same attribute columns, same geometry type).

---

## Sequencing

1. **Tier A done** — CPU environment and checkpoint validated, matches the GPU baseline exactly.
2. **C0a/C0b resolved** — GEE access worked; the user chose reference polygons as the bedrock
   source.
3. **Tier B done** — inference confirmed in the real deployment layout; truncation/screening no-op
   confirmed, with a more precise root cause than previously documented (missing `intersect`
   module, not just missing bedrock polygons).
4. **Tier C in progress (as of 2026-10-05):** C1a–C1d done. Stage 2 is complete for all four sensors,
   with Landsat-8 (deviation 2, seeded `para.ini`). C2b `intersect.py` vendored. Next: C2 (polygon
   split) and C2c (helper audit), then C3. The `batch_download_direct.py` in-place edit is resolved:
   the source is restored and the edit is `Dockerfile.gee-download` deviation 6. It touches only the
   Sentinel blocks; the Landsat-8 download used the original loop.
5. Tier D once C4 shows numbers in the expected range.

## Definition of done for Phase 1

At least one glacier has a screened, truncated terminus trace produced by this pipeline, compared
numerically against `Termini/GID<n>.shp`, with every deviation from the original source (CPU torch
substitution, any derived bedrock polygons, GEE sensor choice) logged in one auditable place. Only
then does Phase 2 (v2) start.
