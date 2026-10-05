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

The map layers can be toggled individually: the satellite image (the `upsample/` image the network
saw), the raw inference trace (yellow, dashed), the final or screened trace (red), the published
trace for the same date and satellite (cyan), and the cutting polygon (white, dashed). Use ↑/↓ or
←/→ to step through dates. Filter by sensor and by status.

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
