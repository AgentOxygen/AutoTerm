# Pipeline architecture

How data moves through AutoTerm. Read `science-context.md` for why each stage exists.

## Execution model

AutoTerm is not a library. It has no importable API and no single entry point. It is a set of Bash
scripts that loop over glacier IDs and shell out to Python scripts, GDAL command line tools, and
GMT plotting commands.

Every stage follows the same pattern:

1. A `batch_*.sh` script reads a plain text list of glacier IDs.
2. For each glacier, it changes into that glacier's data directory.
3. It reads configuration values by running `parameters.py -p para.ini <key>` and capturing stdout.
4. It calls a Python script or a GDAL command per file.

Configuration is passed as command line arguments and through `para.ini` files. No environment
variables are read except `CUDA_VISIBLE_DEVICES`.

## Stages

| Stage | Directory | Entry point | Input | Output |
|---|---|---|---|---|
| 1. Acquisition | `GEE/` | `batch_download_direct.py` | Glacier ID list with bounding boxes | GeoTIFF per image, in per-sensor folders |
| 2. Preprocessing | `batch_preprocess_images/` | `haha.sh` lists the order; `batch_process.sh` does the work | Raw GeoTIFFs | Reprojected, cropped, histogram stretched, upsampled GeoTIFFs |
| 3. Inference and screening | `batch_inference_termini/` | `batch_inference_plot_mv_figure_dir.sh <network.tar>` | Preprocessed GeoTIFFs | Screened terminus traces as GMT, KML, and shapefile |
| 3a. Segmentation | `pytorch-deeplab-xception/` | `train.py`, `inference.py` | Image patches | Per-patch probability GeoTIFFs |
| 4. Uncertainty | `MC_dropout/` | `batch_quantify_MC_dropout_uncertainty.sh <network.tar>` | Preprocessed GeoTIFFs and reference traces | Per-glacier uncertainty text file |
| 5. Publication | `merge_shp/` | `batch_merge_shapefile.sh <dir>` | Per-date traces plus uncertainty table | One shapefile per glacier with attributes |

`data_processing/` holds shared helpers called from all stages. It is not a stage.

## Stage 2, preprocessing, in order

The order is recorded in `batch_preprocess_images/haha.sh` and the `note` file:

1. `build_folder_structure.sh` creates the per-glacier directory tree. Not in the root repository;
   see `repository-map.md`.
2. `batch_read_box_process.sh` reads each glacier's region of interest and calls `batch_process.sh`.
3. `batch_process.sh <GID> <xmin> <ymin> <xmax> <ymax> <xL> <yL> <xS> <yS>` dispatches to one
   `batch_process_<sensor>_images.sh` per sensor, then runs `batch_stretch.sh`.
4. Each per-sensor script runs `gdalwarp` to reproject to EPSG:4326 and clip to the region of
   interest at a fixed pixel size, then `gdal_translate -b 1` to take the single band. When two
   scenes share a date, `gdal_merge.py` combines them.
5. `batch_remove_partial_images.sh` drops scenes that only partially cover the region of interest.
6. `batch_stretch.sh` applies histogram normalization, writing `after_merge/` to `hist_eq/`.
7. `batch_upsample.sh` upsamples if the image is narrow. If `x_size` is below 1000, it runs
   `gdalwarp -r cubic` with an integer factor of `1000/x_size + 1`. Otherwise it symlinks `hist_eq/`
   to `upsample/`.
8. `batch_generate_para_upsample.sh` writes `para_upsample.ini` with the new image dimensions.
9. `batch_generate_truncating_polygon.sh` shrinks the region of interest into a truncating polygon.
   The paper and the operating procedure both note this polygon is sometimes wrong and must be
   drawn by hand.

## Stage 3, the core loop, in order

`batch_inference_plot_mv_figure_dir.sh <network.tar>` reads `Glacier_ID_list_temp.txt` and runs the
following per glacier. A glacier with no cutting polygon is skipped with a message.

1. `batch_inference.sh <glacier_dir> <polygon> <network>` runs inference over every sensor
   subdirectory. It prefers `upsample/` and falls back to `hist_eq/` if `upsample/` is empty.
2. `batch_truncate_termini.sh` trims each trace where it crosses the bedrock or ice mask boundary,
   leaving only the calving front.
3. `batch_plot_truncate.sh` produces GMT figures for visual checking.
4. `batch_abandon_empty_results.sh` removes traces with no geometry.
5. Screening loop one, at most 3 iterations:
   - `batch_smoothness_truncate.sh` computes polygon complexity per trace.
   - `batch_cal_length_truncate.sh` computes trace length.
   - `batch_abandon_results.sh` applies thresholds and moves failures to `abandon/`.
   - The loop breaks early when fewer than 15 new traces were abandoned in that iteration.
6. `put_together_truncate_termini.sh` gathers per-sensor traces into one directory.
7. `batch_remove_duplicate.sh` keeps one trace per date per sensor.
8. Screening loop two, at most 10 iterations:
   - `batch_merge.sh` builds the terminus position time series.
   - `batch_area_cal2.sh` computes the area enclosed between temporally adjacent traces.
   - `batch_abandon_results_time_series.sh` applies the threshold and moves failures to `abandon/`.
   - The loop breaks early when fewer than 1 new trace was abandoned in that iteration.
9. A third screening loop for flowline projection variation exists in the script but is commented
   out, and the two scripts it calls are not in the repository.
10. `batch_area_cal.sh` computes final areas. Not in the root repository; see `repository-map.md`.
11. `batch_split_data_by_name.sh` separates results by sensor.
12. `batch_calculate_offset_sentinel.sh` applies the Sentinel-1 georeferencing correction.
13. `batch_calculate_error.sh` computes per-trace error.
14. `batch_plot_time_series.sh` produces the terminus variation figures.
15. `batch_mv_abandon_duplicate.sh` and `batch_mv_truncate_figure_dir.sh` tidy the output layout.

Rejected traces are moved to an `abandon/` directory. They are never deleted.

## Inference and post-processing, command by command

`preparing_influence.sh <dir>` runs `find ${path}/*.tif > list/test.txt`, then splits that list with
`split -dl 50 -a 4 --additional-suffix=.txt`, producing 50-line chunks named `list/test0000.txt`,
`list/test0001.txt`, and so on. It deletes any previous `list/*test*.txt` first.

The `find ${path}/*.tif` form relies on shell globbing before `find` runs, so it fails with an
argument list error on a directory holding a very large number of images, and fails with "No such
file or directory" on an empty directory rather than producing an empty list.

`exe_inference.sh <cutting_polygon.gmt> <network.tar>` then does the following.

For each chunk file, run `inference.py` with `--backbone drn --workers 0 --cuda --useBN
--batchSize 1 --resume <network>`. This performs sliding window patch inference and writes one
georeferenced GeoTIFF per patch into `test_output/`.

Then, for each source image:

1. `gdal_merge_average.py` mosaics the patch outputs into a two band raster. Band 1 is the sum of
   predictions, band 2 is the count of overlapping patches.
2. `gdal_translate -ot Float32 -b 1` extracts the sum band.
3. `gdal_translate -ot Float32 -b 2` extracts the weight band.
4. `gdal_calc.py --calc="A/B"` divides sum by weight, producing the mean probability per pixel.
5. `gdal_calc.py --calc="255*(A>0.5)"` thresholds at 0.5, producing a binary mask.
6. `gdal_polygonize.py -8` vectorizes the mask to a shapefile.
7. `rm_small_polygon.py` drops polygons smaller than 100,000 square metres, which is 0.1 square
   kilometres. It reprojects each polygon to polar stereographic before measuring, so the cutoff is
   a real area and not a count of square degrees.
8. `ogr2ogr -f 'GMT'` converts to GMT ASCII, then `sed -i 1,11d` strips the 11 line header.
9. `point_in_polygon.py` clips the trace to the cutting polygon, keeping only the calving front side.
10. `gmt gmtset FORMAT_GEO_OUT=D` then `gmt gmt2kml -Fl` produces a KML.
11. `ogr2ogr -f "ESRI Shapefile"` converts the KML to a shapefile.

Intermediate rasters are deleted at the end of each iteration, except `*_out_temp.tif`, the
pre-threshold probability raster.

## Stage 4, MC dropout, in order

`batch_quantify_MC_dropout_uncertainty.sh <network.tar>` calls:

1. `batch_MC_dropout.sh`, which runs `exe_inference_MC_dropout.sh` three times per image using
   `inference_MC_dropout.py --backbone drndropout`. Dropout stays active at inference, so each run
   gives a different trace.
2. `MC_dropout_uncertainty.sh`, which for each date reverses the MC trace with `invert_data2.py`,
   concatenates it with the reference trace to close a polygon, and measures the enclosed area with
   `calculate_abs_area.py`.
3. `batch_average_MC_dropout_uncertainty.sh`, which averages to one value per glacier and writes
   `MC_uncertainty_<GID>.txt`.

The reversal in step 2 is required because both traces are open polylines running the same
direction. Concatenating them without reversing one produces a self-intersecting figure rather than
a closed area.

## Stage 5, merge, in order

`batch_merge_shapefile.sh <dir>` iterates every file matching
`<date>_<satellite>_<GID>_*.shp`. For each, `get_uncertainty.py` looks the uncertainty up in
`uncertainty_all_lola.txt`, then `merge_shapefile.py` appends the geometry to the glacier's output
shapefile with attributes `Date`, `Glacier ID`, `Satellite`, and `Error`.

## What the paper describes but this repository does not implement

| Paper section | Feature | Code status |
|---|---|---|
| 3.2 | Converting TermPicks polylines into polygon labels | Absent |
| 3.4, metric 1 | Flowline intersection screening | Scripts absent, call site commented out |
| 3.7 | Ice and ocean mask generation | Absent |
| 5.5 | Automatic region of interest update from centerline | Absent |
| 5.5 | Glacier ID updates on terminus split or merge | Absent |
