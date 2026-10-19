# Components

Per-directory reference. Use `repository-map.md` to decide which copy of a file to edit, and this
document to learn what a given script does.

Common conventions across all stages: configuration comes from command line arguments and from
`para.ini`; no environment variable is read except `CUDA_VISIBLE_DEVICES`; Python helpers take
`--input` and `--output` style flags; Bash drivers take positional arguments.

## `GEE/` — acquisition

| File | Purpose |
|---|---|
| `batch_download_direct.py` | Reads `Glacier_ID_list_download_1.txt`, builds an `ee.Geometry.Rectangle` per glacier, downloads each image with `getDownloadURL()` and `requests` into `<GID>_<satellite>/` |
| `batch_download.py` | Same filters, but exports to Google Drive with `geetools.batch.Export`. Use when an image exceeds the 35 MB direct download limit |
| `batch_download_historical.py` | Landsat 5 and 7 era |
| `Glacier_ID_list.txt` | 290 Greenland glaciers with longitude and latitude bounding boxes |

Collections and bands requested:

| Collection | Band | Resolution | Filter | Active in `batch_download_direct.py` |
|---|---|---|---|---|
| `LANDSAT/LC08/C01/T1` | B8 | 15 m | `CLOUD_COVER` below 60 | No, commented out |
| `LANDSAT/LE07/C01/T1` | B8 | 15 m | `CLOUD_COVER` below 60 | No, commented out |
| `LANDSAT/LT05/C01/T1` | B3 | 30 m | `CLOUD_COVER` below 60 | No, commented out |
| `COPERNICUS/S1_GRD` | HH | 10 m | IW mode, resolution H, ascending and descending stored separately | Yes |
| `COPERNICUS/S2` | B4 | 10 m | `CLOUDY_PIXEL_PERCENTAGE` below 60 | Yes |

Two behaviours to be aware of. Sensor selection is a manual comment-and-uncomment toggle rather than
a flag, so no single run fetches all five sensors; the published version of this file had the
inverse set enabled, and `pitfalls.md` has the comparison. Direct download also fails for images
above 35 MB, which happens for large glaciers such as GID85.

`batch_download.py` has its Landsat block active, so it is the script that currently reflects the
multi-sensor design.

## `batch_preprocess_images/` — preprocessing

`haha.sh` and the `note` file record the intended run order. See `overview.md` for the full ordered
sequence.

| File | Purpose |
|---|---|
| `batch_read_box_process.sh` | Looks up each glacier's region of interest and calls `batch_process.sh` |
| `batch_process.sh` | Takes `<GID> <xmin> <ymin> <xmax> <ymax> <xL> <yL> <xS> <yS>`, dispatches to the per-sensor scripts, then runs `batch_stretch.sh` |
| `batch_process_Landsat-8_images.sh` | Per image: `gdalwarp` to EPSG:4326 clipped to the region of interest at fixed pixel size, `gdal_translate -b 1`, and `gdal_merge.py` when two scenes share a date |
| `batch_process_Sentinel-1_images.sh` | As above, for Sentinel-1 |
| `batch_process_Sentinel-2_images.sh` | As above, for Sentinel-2 |
| `batch_process_historical.sh` | As above, for Landsat 5 and 7 |
| `batch_remove_partial_images.sh` | Drives `remove_partial_images.py` |
| `remove_partial_images.py` | Drops scenes that only partially cover the region of interest |
| `get_imagesize.py` | Reports raster dimensions, used to decide upsampling |
| `get_roi.py` | `--id <n>` looks the region of interest up in `ROI_new_ID.txt`. The path to that file is hardcoded |
| `batch_upsample.sh` | If `x_size` is below 1000, runs `gdalwarp -r cubic` with integer factor `1000/x_size + 1`. Otherwise symlinks `hist_eq/` to `upsample/` |
| `batch_generate_para_upsample.sh` | Writes `para_upsample.ini` with post-upsampling dimensions |
| `batch_generate_truncating_polygon.sh` | Shrinks the region of interest into a cutting polygon. Output is sometimes wrong and must be replaced by hand |
| `parameters.py` | The `key = value` configuration reader used by every stage. Authored by Lingcao Huang, 2016 |
| `ROI_new_ID.txt` | Region of interest table |

`parameters.py` has two interfaces. Python callers use `get_string_parameters`,
`get_digit_parameters`, and `get_bool_parameters`. Bash callers invoke it as
`parameters.py -p <file> <key>`, which prints the value to stdout. This subprocess call is how every
shell script in the pipeline reads configuration.

`batch_stretch.sh` performs histogram normalization, writing `after_merge/` into `hist_eq/`. It
lives in `data_processing/`, not here.

## `pytorch-deeplab-xception/` — the network

A vendored copy of jfzhang95/pytorch-deeplab-xception, MIT licensed, modified for single-channel
input and `num_classes=1`.

| File | Purpose |
|---|---|
| `train.py` | `train.py <dataroot> <para> <list>`. Flags include `--backbone {resnet,xception,drn,mobilenet}`, `--out-stride`, `--lr`, `--batch-size`, `--epochs`, `--loss-type`, `--patience`, `--resume`. Splits 95 percent train and 5 percent validation, writes `Saver` and `TensorboardSummary` output under `run/`, applies early stopping through `pytorchtools.EarlyStopping` |
| `train_dropout.py` | Training for the MC dropout model |
| `inference.py` | Sliding window patch inference. Each patch is written as a georeferenced uint8 GeoTIFF into `test_output/`, carrying the window transform from the source raster |
| `inference_MC_dropout.py` | Same, with `--backbone drndropout`, leaving dropout active at inference |
| `datasetRS_Mar15.py` | The dataset module `inference.py` imports |
| `datasetRS_MP.py` | The `pathos` multiprocess variant that `train.py` imports |
| `datasetRS.py`, `datasetRS_test.py` | Earlier variants, retained |
| `split_image.py` | `sliding_window` tiles a scene into patches. See `pitfalls.md` for what the overlay parameter actually does |
| `modeling/` | `deeplab.py`, `aspp.py`, `decoder.py`, and `backbone/{resnet,xception,drn,mobilenet}.py`, each with a `*_dropout.py` twin. Also `sync_batchnorm/` |
| `basic_src/` | Lingcao Huang's remote sensing helpers: `RSImage`, `RSImageProcess`, `map_projection`, `io_function`, `basic`. Partly Python 2 |
| `mypath.py` | VOC, SBD, Cityscapes, and COCO paths inherited from upstream. Unused here |

The `RemoteSensingImg` dataset class reads patches through `rasterio` windows rather than loading
whole scenes.

Relevant `para.ini` keys: `train_patch_width`, `train_patch_height`, `train_pixel_overlay_x`,
`train_pixel_overlay_y`, `inf_patch_width`, `inf_patch_height`, `inf_pixel_overlay_x`,
`inf_pixel_overlay_y`, `crop_width`, `crop_height`, `crop_width_test`, `crop_height_test`.

## `batch_inference_termini/` — inference driver and screening

| File | Purpose |
|---|---|
| `batch_inference_plot_mv_figure_dir.sh` | Top level entry point. Takes `<network.tar>`, loops `Glacier_ID_list_temp.txt`. Requires a cutting polygon per glacier |
| `batch_inference.sh` | Runs inference over each sensor subdirectory of one glacier. Prefers `upsample/`, falls back to `hist_eq/` |
| `preparing_influence.sh` | Finds all `.tif` files under a directory, writes `list/test.txt`, splits it into 50-line chunks `list/test0000.txt` onward |
| `exe_inference.sh` | Inference, mosaic, threshold at 0.5, polygonize, drop small polygons, clip to polygon, write GMT, KML, and shapefile. See `overview.md` for the command by command sequence |
| `batch_truncate_termini.sh` | Clips traces to the calving front using bedrock polygons, through `data_processing/truncate_termini.py` |
| `batch_abandon_empty_results.sh` | Removes traces with no geometry |
| `batch_smoothness_truncate.sh` | Computes polygon complexity per trace |
| `batch_cal_length_truncate.sh` | Computes trace length |
| `batch_abandon_results.sh` | Applies smoothness and length thresholds, moves failures to `abandon/` |
| `batch_area_cal2.sh` | Computes area enclosed between temporally adjacent traces |
| `batch_abandon_results_time_series.sh` | Applies the area change threshold |
| `put_together_truncate_termini.sh` | Gathers per-sensor traces into one directory |
| `batch_remove_duplicate.sh` | Keeps one trace per date per sensor |
| `batch_mv_abandon_duplicate.sh` | Moves duplicate rejects |
| `batch_merge.sh` | Builds the terminus position time series |
| `batch_split_data_by_name.sh` | Separates results by sensor |
| `batch_calculate_offset_sentinel.sh` | Sentinel-1 georeferencing correction from same-day optical pairs |
| `batch_calculate_error.sh` | Per-trace error |
| `batch_plot_truncate.sh`, `batch_plot_time_series.sh` | GMT figures for manual quality control |
| `batch_mv_truncate_figure_dir.sh`, `batch_mv_back.sh` | Output layout housekeeping |

Rejected traces are moved into `abandon/`, never deleted. Screening iteration counts and their
early exit conditions are in `overview.md`; the discrepancies with the paper are in `pitfalls.md`.

## `MC_dropout/` — uncertainty

| File | Purpose |
|---|---|
| `batch_quantify_MC_dropout_uncertainty.sh` | Entry point, takes `<network.tar>` |
| `batch_MC_dropout.sh` | Runs three stochastic forward passes per image |
| `exe_inference_MC_dropout.sh` | Inference with `--backbone drndropout` |
| `MC_dropout_uncertainty.sh` | Per date, reverses the MC trace with `invert_data2.py`, concatenates it with the reference trace, and measures the enclosed area with `calculate_abs_area.py` |
| `batch_average_MC_dropout_uncertainty.sh` | Averages to one value per glacier, writes `MC_uncertainty_<GID>.txt` |

## `merge_shp/` — publication output

| File | Purpose |
|---|---|
| `batch_merge_shapefile.sh` | For every `<date>_<satellite>_<GID>_*.shp`, looks up the uncertainty and appends the geometry |
| `merge_shapefile.py` | GeoPandas append. Writes or extends one shapefile per glacier with attributes `Date`, `Glacier ID`, `Satellite`, `Error` |
| `get_uncertainty.py` | Reads `uncertainty_all_lola.txt`, selecting a column by sensor |
| `uncertainty_all_lola.txt` | One row per glacier. Column indices are listed in `conventions.md` |

## `data_processing/` — shared helpers

Small single-purpose command line tools over GMT ASCII traces, plus Bash wrappers that loop them.
All distance and area work reprojects to polar stereographic first.

Geometry and metrics:

| File | Purpose |
|---|---|
| `cal_length.py` | Trace length in metres |
| `calculate_area.py`, `calculate_area2.py` | Area enclosed between traces, two formulations |
| `calculate_abs_area.py` | Absolute enclosed area, summing both sides of any crossing |
| `calculate_area_DOY.py` | Area binned by day of year |
| `calculate_area_mask.py` | Area within a mask |
| `polygon_complexity.py` | Shape complexity, the smoothness screening metric |
| `cal_average_curvature.py` | Mean curvature over every three adjacent points |
| `count_turning_point.py` | Turning point count |

Terminus position:

| File | Purpose |
|---|---|
| `truncate_termini.py` | Clips a trace at the bedrock and ice mask boundary, leaving the calving front |
| `truncate_termini_backup.py` | Earlier variant, retained |
| `calculate_flowline_projection.py` | Projects a trace onto the glacier flowline |
| `calculate_flowline_intersection.py` | Trace and flowline intersections |
| `derivative_flowline_projection.py` | Rate of change of the flowline projection |
| `get_intersection.py` | General polyline intersection |
| `accumulate_area_length.py` | Cumulative area and length |

Screening and statistics:

| File | Purpose |
|---|---|
| `cal_threshold.py` | Upper threshold only, `Q3 + 2 * IQR` |
| `cal_threshold_2.py` | Upper and lower thresholds, coefficient 1.5 |
| `calculate_error.py` | Error between a predicted and a reference trace |
| `calculate_error_length.py` | Error expressed as a length change |
| `find_offset.py` | Sentinel-1 georeferencing offset |
| `find_average.py`, `find_min_max.py`, `find_min_convert_date.py` | Summary statistics |
| `plot_hist.py` | Metric distribution histogram |

Plumbing:

| File | Purpose |
|---|---|
| `invert_data2.py` | Reverses point order in a trace. Required before closing two traces into a polygon |
| `convert_date.py` | Date representation conversion |
| `split_data_by_name.sh` | Separates results by sensor, parsed from the file name |
| `remove_duplicate.sh` | One trace per date per sensor |
| `merge_two_calving2.sh` | Merges two calving front segments |

Preprocessing scripts that live here rather than in `batch_preprocess_images/`:
`batch_stretch.sh`, `batch_process.sh`, `batch_process_Landsat-8_images.sh`,
`batch_process_Sentinel-1_images.sh`, `batch_process_Sentinel-2_images.sh`,
`batch_process_historical.sh`. The operating procedure requires these to be copied into a
`data_processing/` directory on `PATH`.

Plotting, all GMT based: `result_plot.sh`, `result_plot_mask.sh`, `plot_time_series.sh`,
`plot_time_series_all.sh`, `plot_time_series_all_distance.sh`,
`plot_time_series_before_S1_correction.sh`, `plot_time_series_historical.sh`,
`batch_plot_result.sh`, `batch_plot_result_2.sh`.

## `FrontDL3/` — submodule

A fork of the upstream segmentation repository, runnable on modern Python and on CPU. Its layout
differs from the root repository.

| Path | Contents |
|---|---|
| `FrontDL3/script/` | `gdal_merge_average.py`, `rm_small_polygon.py`, `point_in_polygon.py`, `parameters.py`, `split_image.py`, `datasetRS*.py`, `basic_src/`. Three of these are called by the root pipeline but absent from it |
| `FrontDL3/pytorch-deeplab-xception/` | The network, with modern Python and CPU fixes applied |
| `FrontDL3/pre-processing/` | Sensor-specific preprocessing including ALOS, ENVISAT, and TerraSAR-X, which the root repository does not cover |
| `FrontDL3/post-processing/` | Per-glacier test scripts for Jakobshavn, Helheim, and Kangerdlugssuaq, plus truncation polygons |
| `FrontDL3/quantification_error_analysis/` | Error analysis, including `batch_area_cal.sh`, which the root pipeline calls but does not contain |
| `FrontDL3/image_augmentation/` | `image_augment.py` and `image_augment.sh`, the rotation and flip augmentation |
| `FrontDL3/train/`, `FrontDL3/ground_truth/` | One sample image and one sample label, enough to exercise the inference path |
| `FrontDL3/exe.sh` | Training invocation examples with concrete flag values |
| `FrontDL3/exe_inference.sh` | Inference driver, with `set -euo pipefail` added by the fork |
| `FrontDL3/build_folder_structure.sh` | Creates the per-glacier directory tree. Called by the root preprocessing stage but absent from it |
| `FrontDL3/para.ini` | A complete working configuration file, useful as a reference for key names and values |
