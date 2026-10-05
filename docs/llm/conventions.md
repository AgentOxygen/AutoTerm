# Data conventions

Formats, names, and coordinate systems. Read this before writing code that parses or produces
pipeline data.

## Glacier identifiers

A glacier is identified by the string `GID<n>`, for example `GID1`, `GID85`, `GID164`.

Two spellings of the same identifier appear and they are not interchangeable:

| Spelling | Example | Where it is used |
|---|---|---|
| `GID<n>` | `GID1` | Directory names, glacier list files |
| `GID_<n>` | `GID_1` | File names inside a glacier directory, such as the cutting polygon |

`batch_inference_plot_mv_figure_dir.sh` converts between them with
`ID=${GID#*GID}` followed by `GID2=GID_${ID}`. Code that builds paths must do the same conversion.

## Region of interest files

A region of interest is a longitude and latitude bounding box, one glacier per line.

| File | Format | Notes |
|---|---|---|
| `GEE/Glacier_ID_list.txt` | `GID<n> xmin ymin xmax ymax` | 290 glaciers. The paper reports 295 |
| `batch_preprocess_images/ROI_new_ID.txt` | Same | Read by `get_roi.py`, which has the path hardcoded |
| `Glacier_ID_list_temp.txt` | One `GID<n>` per line, no coordinates | The work list. Read by the stage 3 driver. Not in the repository; you create it |
| `Glacier_ID_list_download_1.txt` | `GID<n> xmin ymin xmax ymax` | Read by `GEE/batch_download_direct.py`. Not in the repository |

The operating procedure and the download script disagree on column order. The docx says
`Glacier name/ID xmin xmax ymin ymax`. `GEE/Glacier_ID_list.txt` is in `xmin ymin xmax ymax` order.
Check the actual file before relying on either.

## Image file names

The convention is `<YYYYMMDD>_<Satellite>_<GID>_stretch.<ext>`, for example
`20160302_Landsat-8_GID1_stretch.tif`.

Dates and sensor names are extracted throughout the pipeline with `cut -d '_'` on the file name.
There is no metadata sidecar and no database. The file name is the metadata.

Consequences for any code you write:

1. Never introduce an underscore into a satellite name or a glacier ID.
2. Never rename an output file without checking every `cut -d '_'` call site downstream.
3. A file whose name does not have the expected number of underscore-delimited fields will not
   error. It will produce a wrong date or a wrong sensor silently.

Satellite names in use: `Landsat-5`, `Landsat-7`, `Landsat-8`, `Sentinel-1_A`, `Sentinel-1_D`,
`Sentinel-2`. Sentinel-1 ascending and descending are kept separate because their georeferencing
differs.

## Per-glacier directory layout

Inside a glacier directory such as `<data_path>/GID1/`:

| Subdirectory | Contents | Created by |
|---|---|---|
| `GID_1_Landsat-8/` and one per sensor | That sensor's images and results | `build_folder_structure.sh` |
| `original_image/` | Raw downloads | Stage 1 |
| `temp/` | Reprojection and crop intermediates | Stage 2 |
| `after_merge/` | Same-date scenes merged | Stage 2 |
| `hist_eq/` | Histogram stretched | Stage 2 |
| `upsample/` | Size normalized, or a symlink to `hist_eq/` | Stage 2 |
| `polygon/` | `GID_1_cutting_polygon.gmt` or `GID_1_cutting_polygon_shrink.gmt` | Stage 2 |
| `test_output/` | Per-patch inference rasters | Stage 3 |
| `post_output/` | Mosaicked and thresholded rasters | Stage 3 |
| `post_process_shape/<network>/` | Vectorized polygons | Stage 3 |
| `post_process_gmt/` | GMT ASCII before clipping | Stage 3 |
| `in_polygon_gmt/<network>/` | Traces clipped to the cutting polygon | Stage 3 |
| `truncate_termini/<network>/` | Final traces | Stage 3 |
| `truncate_termini/<network>/abandon/` | Traces rejected by screening | Stage 3 |
| `truncate_termini/<network>_time_series/` | Terminus variation series | Stage 3 |
| `para.ini` | Per-glacier configuration | Stage 2 |
| `para_upsample.ini` | Same, with post-upsampling image dimensions | Stage 2 |

`<network>` is the checkpoint file name with the `.tar` suffix removed. The scripts compute it as
`temp=${network%.tar*}`.

Stage 3 prefers `upsample/` and falls back to `hist_eq/` when `upsample/` is empty.

## Configuration files, para.ini

`para.ini` is not INI format. It has no sections and no INI parser reads it. It is plain
`key = value` text parsed by `parameters.py`.

Bash scripts read one value at a time by invoking the parser as a subprocess and capturing stdout:

```
value=$(python2 /path/to/parameters.py -p para.ini working_root)
```

`parameters.py` exposes `get_string_parameters`, `get_digit_parameters`, and
`get_bool_parameters` for Python callers.

Global keys, set once in the working root:

| Key | Meaning |
|---|---|
| `working_root` | Full path of the Front_DL3 code directory |
| `data_path` | Full path of the data directory holding all glacier folders |
| `codes_dir` | Full path of the helper script directory, normally `<working_root>/script` |
| `b_use_rectangle` | Passed through to the patch splitter |
| `train_patch_width`, `train_patch_height` | Patch size during training, 320 by 240 |
| `train_pixel_overlay_x`, `train_pixel_overlay_y` | Patch extension during training, 320 and 240 |
| `inf_patch_width`, `inf_patch_height` | Patch size during inference, 192 by 144 |
| `inf_pixel_overlay_x`, `inf_pixel_overlay_y` | Patch extension during inference, 384 and 288 |
| `crop_width`, `crop_height` | 960 by 720 |
| `crop_width_test`, `crop_height_test` | 960 by 720 |

Per-glacier keys, in each glacier's `para.ini`:

| Key | Meaning |
|---|---|
| `x_size_L`, `y_size_L` | Image dimensions for the large-pixel sensors |
| `x_size_S`, `y_size_S` | Image dimensions for the small-pixel sensors |
| `xmin`, `ymin`, `xmax`, `ymax` | Region of interest bounds |

`pixel_overlay` is not a stride. See `pitfalls.md` for what it actually does.

## Trace format, GMT ASCII

The interchange format for terminus traces is GMT ASCII with a `.gmt` extension. Most scripts in
`data_processing/` read it with `np.loadtxt` and write it with `np.savetxt`.

Properties:

1. Two whitespace-separated columns, longitude then latitude, in decimal degrees.
2. One point per line, ordered along the trace.
3. No header. `ogr2ogr -f 'GMT'` writes an 11 line header, and `exe_inference.sh` removes it
   immediately with `sed -i 1,11d`.
4. Written with `fmt='%.7f'`, so roughly 1 cm precision at these latitudes.

Because `np.loadtxt` is used, a `.gmt` file containing a multi-segment separator, a comment line, or
a header will raise rather than parse. Any code producing a `.gmt` file must produce bare numbers.

## Coordinate systems

| Purpose | Projection |
|---|---|
| Storage and interchange | Geographic, EPSG:4326, longitude and latitude in degrees |
| Preprocessed rasters | EPSG:4326, set by `gdalwarp` in the per-sensor scripts |
| All distance and area computation | Polar stereographic, `+proj=stere +lat_0=90.0 +lat_ts=70 +lon_0=-45` |

The polar stereographic string is equivalent to EPSG:3413, the standard Greenland projection. It is
written literally as a `pyproj.Proj` string in every script that computes a length or an area,
including `cal_length.py`, `truncate_termini.py`, and the `calculate_area*.py` family.

The rule the code follows: never measure a distance in degrees. Convert to polar stereographic
first, measure in metres, and report metres.

## Uncertainty table

`merge_shp/uncertainty_all_lola.txt` is a whitespace table, one row per glacier. `get_uncertainty.py`
selects a column by sensor:

| Column index | Sensor |
|---|---|
| 2 | Landsat 5 |
| 3 | Landsat 7 |
| 4 | Landsat 8 |
| 5 | Sentinel-1 |
| 6 | Sentinel-2 |
| 7 | Duplicate trace uncertainty |

Columns 2 through 6 are MC dropout values. Column 7 is the duplicate trace value. This matches the
paper's statement that each glacier carries six uncertainty measures.

The row is selected as `uncertainty_all[int(GID) - 1, :]`, so the table must be ordered by numeric
glacier ID starting at 1, with no gaps. A missing glacier shifts every row below it.

`get_uncertainty.py` combines the two values rather than reporting them separately:

| MC dropout value | Duplicate value | Reported uncertainty |
|---|---|---|
| Nonzero | Nonzero | Mean of the two |
| Nonzero | Zero | The MC dropout value |
| Zero | Nonzero | The duplicate value |
| Zero | Zero | The string `N/A` |

Zero is used as the missing-data marker. A genuine uncertainty of zero cannot be represented.

`get_uncertainty.py` expects satellite names with no hyphen and no ascending or descending suffix:
`Landsat5`, `Landsat7`, `Landsat8`, `Sentinel1`, `Sentinel2`. Directory and file names use the
hyphenated forms `Landsat-5` through `Sentinel-2`, and split Sentinel-1 into `Sentinel-1_A` and
`Sentinel-1_D`. Code passing a sensor name into this script must convert. An unrecognised name
prints `N/A` and calls `os._exit()` with no argument, which raises `TypeError` rather than exiting
cleanly.

## Output shapefile attributes

`merge_shapefile.py` writes one shapefile per glacier with these attribute fields:

| Field | Content |
|---|---|
| `Date` | Trace date |
| `Glacier ID` | `GID<n>` |
| `Satellite` | Source sensor name |
| `Error` | Uncertainty in metres for that trace |

The paper states the published date format is `YYYY-MM-DD`, while file names use `YYYYMMDD`.
`data_processing/convert_date.py` exists to bridge date representations.
