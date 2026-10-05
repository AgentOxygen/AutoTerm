# Repository map

This document answers one question: which file do I edit?

## Two copies of the deep learning code

There are two copies of the segmentation code in this repository. They are not identical and they
have different purposes.

| Copy | Path | Origin | Runs on CPU | Use it when |
|---|---|---|---|---|
| Root copy | `pytorch-deeplab-xception/` | Committed in "The pipeline upload" | No | You are working on the full AutoTerm pipeline, including preprocessing, screening, MC dropout, and merge stages |
| Submodule | `FrontDL3/pytorch-deeplab-xception/` | Fork at `github.com/AgentOxygen/FrontDL3` | Yes | You need to actually execute inference and see output |

The submodule is a fork of `github.com/enzezhang/FrontDL3`. It branches from upstream commit
`5684a19` ("update to python3") and adds six commits that make the code run on a modern system:

| Commit | Change |
|---|---|
| `cb01a8c` | Removed a `scipy.ndimage.imread` import that no longer exists in scipy 1.3 and above |
| `7692ed3` | Fixed a tab-indented line that Python 3 rejects with TabError |
| `72c509c` | Replaced the original author's hardcoded home directory paths with container paths |
| `8db51d6` | Changed the pinned GPU from device 1 to device 0 |
| `7e80443` | Avoided a multiprocessing failure under newer Python by using zero dataloader workers |
| `6ec56ca` | Made `--cuda` optional, so inference runs on CPU |
| `b550fe1` | Made the inference shell scripts exit on error |

The root copy has none of these fixes. `pytorch-deeplab-xception/inference.py` calls `.cuda()`
unconditionally and requires a GPU.

If you fix a bug that exists in both copies, fix it in both, or state clearly which one you fixed.

## Scripts the pipeline calls but the root repository does not contain

The root pipeline scripts call these by name. They are not in the root directories.

| Script | Called from | Found in submodule at |
|---|---|---|
| `gdal_merge_average.py` | `batch_inference_termini/exe_inference.sh` | `FrontDL3/script/gdal_merge_average.py` |
| `rm_small_polygon.py` | `batch_inference_termini/exe_inference.sh` | `FrontDL3/script/rm_small_polygon.py` |
| `point_in_polygon.py` | `batch_inference_termini/exe_inference.sh` | `FrontDL3/script/point_in_polygon.py` |
| `build_folder_structure.sh` | `batch_preprocess_images/haha.sh` | `FrontDL3/build_folder_structure.sh` |
| `batch_area_cal.sh` | `batch_inference_termini/batch_inference_plot_mv_figure_dir.sh` | `FrontDL3/quantification_error_analysis/batch_area_cal.sh` |

The submodule supplies all five. When wiring the pipeline together, source them from the submodule
rather than writing new ones.

These are not in the root or the submodule, but `downloads/enze/Front_DL3/` supplies most of them.
Only two remain unaccounted for anywhere, and **both are referenced solely from commented-out
lines**, so neither blocks any live code path.

| Script | Called from | Call site live | Available in `downloads/enze/Front_DL3/` |
|---|---|---|---|
| `batch_plot_truncate_MC_dropout.sh` | `MC_dropout/batch_MC_dropout.sh` line 147 | Yes | Yes, at the root |
| `temp_plot.sh` | `MC_dropout/batch_quantify_MC_dropout_uncertainty.sh` line 16 | No | Yes, at the root |
| `batch_abandon_results_proj_variation.sh` | `batch_inference_plot_mv_figure_dir.sh` | No | Yes, at the root |
| `calculate_area_length.py` | `data_processing/batch_area_cal_DOY.sh` line 25 | No | No |
| `batch_cal_flowline_proj_variation.sh` | `batch_inference_plot_mv_figure_dir.sh` | No | No |

Net effect: **every script on a live code path is now available.** The author's directory closed
the last real gap, `batch_plot_truncate_MC_dropout.sh`, which previously blocked stage 4 plotting.
They are only found if `data_processing/` is on `PATH`, because the step scripts call them by bare name
(see `pitfalls.md`). Two versions of the stage 3 driver exist: the repo's
`batch_inference_termini/batch_inference_plot_mv_figure_dir.sh`, which is the one used, and the author's later
working copy. The working copy adds flowline-intersection screening, which needs
`batch_cal_flowline_intersection_num.sh` and hand-made flowlines; neither is in any archive.

Prefer `downloads/enze/Front_DL3/` over the submodule when a script exists in both, since that copy
is the one the published results were produced with.

## Near-duplicate files that are not redundant

Do not delete these. Different entry points import different ones.

| Group | Files | Which one is live |
|---|---|---|
| Dataset loaders | `datasetRS.py`, `datasetRS_Mar15.py`, `datasetRS_MP.py`, `datasetRS_test.py` | `inference.py` imports `datasetRS_Mar15`. `train.py` imports `datasetRS_MP`, the `pathos` multiprocess variant |
| Training scripts | `train.py`, `train_dropout.py`, `train_backup.py` | `train.py` for normal training, `train_dropout.py` for the MC dropout model |
| Terminus truncation | `truncate_termini.py`, `truncate_termini_backup.py` | `truncate_termini.py`, called by `batch_truncate_termini.sh` |
| Area calculation | `calculate_area.py`, `calculate_area2.py`, `calculate_area_DOY.py`, `calculate_area_mask.py`, `calculate_abs_area.py` | All five are live. They compute different quantities, not the same quantity five ways |
| Threshold calculation | `cal_threshold.py`, `cal_threshold_2.py` | Both are live. `cal_threshold.py` returns one upper bound; `cal_threshold_2.py` returns upper and lower. See `pitfalls.md` for the coefficient difference |
| Model backbones | `modeling/backbone/*.py` and their `*_dropout.py` twins | Both. The dropout twins are used by MC dropout inference |

## Directory purpose at a glance

| Path | Contains | Pipeline stage |
|---|---|---|
| `GEE/` | Google Earth Engine download scripts | 1, acquisition |
| `batch_preprocess_images/` | Reprojection, cropping, merging, histogram stretch, upsampling | 2, preprocessing |
| `pytorch-deeplab-xception/` | DeepLabv3+ network, training, inference | 3a, segmentation |
| `batch_inference_termini/` | Inference driver, post-processing, screening | 3, the core loop |
| `MC_dropout/` | Monte Carlo dropout uncertainty | 4, uncertainty |
| `merge_shp/` | Assembles per-date traces into one shapefile per glacier | 5, publication output |
| `data_processing/` | Shared geometry, statistics, and plotting helpers | Called from every stage |
| `FrontDL3/` | Git submodule, runnable fork of the upstream segmentation repository | Reference implementation |
| `src/autoterm/` | Intended Python package. Currently a stub | Refactor target, not functional |
| `docs/llm/` | This documentation | Not executed |

## Files at the repository root

| File | Status |
|---|---|
| `manuscript.md` | The published paper. Read for intent |
| `AutoTerm Pipeline.docx` | The author's operating procedure. Read for the intended setup sequence |
| `Dockerfile.frontdl3` | GPU inference image (cu130, pinned). Verified on an RTX 5070 |
| `Dockerfile.frontdl3-cpu` | CPU inference image, built from the `FrontDL3/` submodule |
| `Dockerfile.gee-download` | Stage 1 download. Deviations 2–5 via `gee-landsat8-patch.py`, 6 via `gee-resume-patch.py` |
| `Dockerfile.preprocess` | Stage 2 on ubuntu:18.04. `preprocess-entrypoint.sh` builds the layout; `preprocess-seed-para.sh` is deviation 2 |
| `Dockerfile.stage3`, `stage3-host.sh` | Stage 3 (CPU or GPU build) and its host runner |
| `vendor/intersect/` | Vendored `intersect.py` for truncation |
| `tools/data_viewer/` | Read-only web viewer for stage 2/3 output |
| `IMPLEMENTATION_PLAN.md` | Step-by-step Phase 1 log and decisions |
| `Dockerfile` | Empty, zero bytes |
| `pyproject.toml` | Declares the `autoterm` package with an empty dependency list |
| `README.md` | One line per directory |
| `LICENSE` | MIT |
| `.gitmodules` | Registers `FrontDL3` |

`.gitignore` covers `downloads/`, `out/`, `tier-b/`, `tier-c/`, `GEE/GID*/`, `.env/` and local Claude settings. Compiled Python artifacts (`*.pyc` and `__pycache__/` from Python 3.6 and
3.8) are committed throughout `pytorch-deeplab-xception/`.

## `downloads/`

Externally obtained archives and the author's own working directory. Not part of the pipeline, not
referenced by any script, and untracked by git. Roughly 14 GB in total.

| Entry | Size | What it is |
|---|---|---|
| `enze/Front_DL3/` | 12 GB | **The original author's actual working directory**, in deployment layout |
| `Termini.zip` | 1.2 GB | **The published terminus dataset**: complete shapefile sets for exactly 295 glaciers |
| `drn54_May5_2022_0.001_batch16_keep_augmentation.tar` | 326 MB | The trained checkpoint |
| `label_shape_TermPicks.zip` | 265 MB | 132,650 files. The generated TermPicks polygon labels, the training set |
| `reference_polygon_new_ID.zip` | 174 MB | 3,748 files. Per-glacier reference polygons used to convert TermPicks polylines into labels |
| `Icemask.zip` | 92 MB | Three GeoTIFFs: `GimpMask_15m_2015_{2018,2019,2020}_compress.tif` |
| `Terminus_variation_time_series.zip` | 88 MB | Published KMZ time series figures, batched by glacier range |
| `AutoTerm.zip` | 950 KB | The published code archive. Adds nothing, see below |
| `Glacier Identification.csv` | 39 KB | 295 glaciers with latitude, longitude, official name, ID, Moon ID, Bjork ID, and **ROI bounding boxes** |
| `uncertainty_all.csv` | 34 KB | Columns `Name,Y,X,L5,L7,L8,S1,S2,Duplicate`. The readable form of `merge_shp/uncertainty_all_lola.txt` |

### `enze/Front_DL3/`, the author's working directory

This is the deployment layout that `AutoTerm Pipeline.docx` describes assembling by hand. It
resolves the "git layout is not the runtime layout" problem by example rather than by instruction.

Structure notes:

1. All the `batch_*.sh` drivers sit **flattened at the root**, not in subdirectories.
2. `script/` exists and holds `gdal_merge_average.py`, `rm_small_polygon.py`, `point_in_polygon.py`,
   `parameters.py`, `split_image.py`, `datasetRS*.py`, and `basic_src/`.
3. `data_processing/` does **not** exist. The docx says to create it and put it on `PATH`; the
   author instead flattened those scripts into the root.
4. `post_output/` is 4.3 GB of leftover intermediate probability rasters, mostly for Hubbard
   Glacier in Alaska. These are byproducts, not inputs.
5. `list/` holds the generated image lists. They reveal the real data root:
   `/home/staff/enze/data1/Greenland_front_Mapping/data/GID199/GID_199_Sentinel-2/upsample/...`
6. `polygon/` and `train/` each contain a single sample file, not a full set.

It supplies eight of the ten scripts the repository lacks. See "Scripts the pipeline calls" above.

### `Termini.zip`, the reference output

295 glaciers, each with a complete `.shp`, `.shx`, `.dbf`, `.prj`, and `.cpg` set, named `GID<n>`.
This is the published product described in the paper: 278,239 traces.

This is the single most important artifact for the project's goal. It is the accuracy reference that
a reproduction run can be compared against, per glacier, and the baseline AutoTerm v2 must match.
Before this archive arrived there was no way to verify pipeline output at all.

### The checkpoint

Despite the `.tar` extension it is **not a tar archive**. It is a PyTorch checkpoint in the modern
ZIP-based format. The upstream README says "Do not untar it", and `tar` will refuse it. Load it with
`torch.load`, and pass it to the scripts with `--resume`.

Verified contents, read directly from the pickle:

| Property | Value |
|---|---|
| Top-level keys | `epoch`, `state_dict`, `optimizer`, `best_pred` |
| `epoch` | 4 |
| Tensors in `state_dict` | 398, split as backbone 342, aspp 36, decoder 20 |
| Backbone layer names | `backbone.layer0` through `backbone.layer8`, the DRN layout. Use `--backbone drn` |
| Input channels | 1, from `backbone.layer0.0.weight` of shape `(16, 1, 7, 7)` |
| Output classes | 1, from `decoder.last_conv.8.weight` of shape `(1, 256, 1, 1)` |
| DataParallel prefix | Absent. No key starts with `module.`, so it loads on a single device or CPU without stripping prefixes |

The single input channel and single output class confirm this is the AutoTerm-modified DeepLabv3+,
not a stock one. Loading it under PyTorch 2.6 or later requires
`TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1`.

Mount this file into a container. Do not copy it into an image layer, and do not commit it.

`downloads/` is untracked and there is no `.gitignore`. Decide deliberately whether to ignore it
before any `git add -A`, since the archive is roughly 950 KB of content already in git history.

## Code authorship

Three authors appear in the code, which explains the mix of styles:

1. Enze Zhang, the paper's first author, wrote the AutoTerm pipeline scripts.
2. Lingcao Huang wrote `parameters.py`, `split_image.py`, and `basic_src/`. These date to 2016 and
   2017 and are the parts still carrying Python 2 idioms.
3. jfzhang95 wrote the original `pytorch-deeplab-xception`, vendored under the MIT license and
   modified for single-channel input and one output class.
