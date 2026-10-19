# AutoTerm output viewer

A small, read-only web app for browsing AutoTerm stage 2/3 output: satellite images with the inferred
terminus traces on top, the published AutoTerm traces for comparison, and where each date dropped
out of the pipeline.

## Run

From the repository root:

```bash
docker build -t autoterm-viewer tools/data_viewer
docker run --rm -p 127.0.0.1:8080:8080 \
  -v "$PWD/tier-c/data:/data:ro" \
  -v "$PWD/downloads/Termini.zip:/published/Termini.zip:ro" \
  autoterm-viewer
```

Then open <http://localhost:8080>.

- `/data` is the stage 2/3 data directory: the one mounted at
  `/home/staff/enze/data1/Greenland_front_Mapping/data` during the pipeline runs. Any folder with
  `GID<n>/GID_<n>_<sensor>/` inside works. For example, `tier-c/smoke/data` is the CPU smoke test.
- `/published/Termini.zip` is optional. It is read in place, with no unzip needed. Without it, the
  published layer is empty.
- `127.0.0.1:` in `-p` keeps the viewer reachable only from your own machine.
- Both mounts are `:ro`, and the container runs as an unprivileged user. The viewer never writes to
  the data.

## What it shows

**Date view.** One row per image date, colour-coded by what happened to it:

| Status | Meaning (where the trace is) |
|---|---|
| Final | in `GID<n>/truncate_termini/<checkpoint>/` |
| Screened: smoothness / length | in `<sensor>/truncate_termini/<checkpoint>/abandon/` |
| Screened: area change | in `GID<n>/truncate_termini/<checkpoint>/abandon/` |
| Duplicate removed | in `GID<n>/truncate_termini/<checkpoint>/duplicate/` |
| Traced, not in final set | in `in_polygon_gmt/<checkpoint>/` but in none of the above |
| No trace produced | image in `upsample/`, no trace |
| Image rejected (stage 2) | image in `hist_eq/abandon/` (more than 10% empty pixels) |

Use ↑/↓ or ←/→ to step through dates. Filter by sensor and by status.

**Map layers.** Each layer is a different pipeline stage for the selected date, and each can be
toggled on its own:

| Layer | Look | What it is | Read from |
|---|---|---|---|
| Satellite image | greyscale | The image the network actually saw: the stage 2 output after clipping, contrast stretch and upsampling, not the raw download | `<sensor>/upsample/` (or `hist_eq/` for images that never reached `upsample/`) |
| Raw trace (inference) | yellow, dashed | The network's output before any checks: the probability raster thresholded at 0.5, polygonized, small polygons (< 0.1 km²) removed, clipped to the cutting polygon | `<sensor>/in_polygon_gmt/<checkpoint>/` |
| Final / screened trace | red | The same trace after truncation and screening. The date's status says whether it was kept or where it was rejected | `GID<n>/truncate_termini/<checkpoint>/`, or the `abandon/` / `duplicate/` folders in the status table |
| Published trace | cyan | The author's published AutoTerm trace for the same date and satellite: the reference | `Termini.zip`, matched on Date + Satellite |
| Cutting polygon | white, dashed | The box around the fjord that traces are clipped to | `GID<n>/polygon/*cutting_polygon*.gmt` |

How to read them together:

- **Red usually sits exactly on yellow.** Screening only keeps or rejects a trace, it never moves it.
  Truncation only changes a trace where a bedrock polygon (`bed_GID<n>_??.gmt`) exists. GID278 has
  none, so its traces pass through unchanged.
- **Yellow/red against cyan is the comparison with the paper.** Gaps of a few pixels are normal: the
  CPU smoke test had a 36 m median distance to the published traces, and the paper reports 37 m between
  duplicate traces of the same day. A trace that follows a different edge entirely is a real
  disagreement.
- **Missing cyan is not an error.** Not every date was published: the author's run screened traces
  out, removed duplicates, and stopped at 2021-10 for Landsat-8/Sentinel-2 and 2022-02 for Sentinel-1.
- **Trace ends should touch the white box.** That is the clip. The published GID278 traces end on it
  too.

**Checkpoint.** A checkpoint is a saved set of trained network weights: the `.tar` file passed to the
stage 3 driver (`batch_inference_plot_mv_figure_dir.sh <checkpoint>.tar`). The name records how
it was trained, e.g. `drn54_May5_2022_0.001_batch16_keep_augmentation`: a DRN-54 backbone, saved on
5 May 2022, learning rate 0.001, batch size 16, with data augmentation. Different checkpoints give
different traces from the same images, so stage 3 writes each one's output into folders named after it
(`in_polygon_gmt/<checkpoint>/`, `truncate_termini/<checkpoint>/`), and several runs can share one data
folder. The selector lists every checkpoint found under any sensor's `in_polygon_gmt/`, and the
first one alphabetically is the default (so `Mar8` before `May5`). Everything on the page (statuses,
raw and final traces, overview) is for the selected checkpoint. The image, the published traces and
the cutting polygon do not depend on it. For GID278 we compare two: `May5_2022` (run first) and
`Mar8_2022` (the one the author's March 2023 production logs used). The one whose traces match the
published set better is probably the one behind the published data.

**Overview.** All final traces for the glacier and checkpoint, coloured by date, with the published
traces faintly behind them.

The map uses longitude and latitude directly, with the x axis scaled by cos(latitude) so shapes
keep their proportions. There are no web map tiles.

## Files

| File | Purpose |
|---|---|
| `app.py` | Standard-library HTTP server plus a small JSON API. It renders GeoTIFFs to PNG (`tifffile`, no GDAL) and parses GMT and shapefiles |
| `static/index.html` | The whole frontend: one page, plain JavaScript |
| `static/leaflet/` | Leaflet 1.9.4, vendored (BSD-2-Clause, see `LICENSE`). sha256 `db49d009…641a` (`leaflet.js`) |
