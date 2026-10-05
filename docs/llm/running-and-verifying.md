# Running and verifying

How to execute code in this repository and how to check that a change worked.

## What can actually be run today

| Target | Runnable | How |
|---|---|---|
| FrontDL3 inference stage | Yes | `Dockerfile.frontdl3`, described below |
| Individual `data_processing/` Python helpers | Yes | Direct invocation with `--input` and `--output` |
| Root `batch_inference_termini/` stage 3 driver | Partly | Scripts and layout are now available in `downloads/enze/Front_DL3/`. Truncation and screening still blocked on bedrock polygons |
| Stage 2 preprocessing | Partly | `build_folder_structure.sh` is available. Needs `gdal_contrast_stretch`, which the container does not install |
| Stage 1 download | Partly | Needs a Google Earth Engine account. ROI boxes for all 295 glaciers are in `downloads/Glacier Identification.csv` |
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
| PyTorch from the cu128 index | The target GPU is sm_120. No PyTorch wheel before 2.7 has kernels for it |
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

The submodule's `exe_inference.sh` adds `set -euo pipefail`, which converts some of these into real
failures. The root copy does not have it.

## Environment notes for this sandbox

- Persistent environment variables go in `/etc/sandbox-persistent.sh`, which is sourced before
  every Bash command. Never add shell completion scripts to it.
- Network access is filtered. A blocked request returns HTTP 403 with a structured body explaining
  which rule blocked it.
- Google Earth Engine stage 1 needs `ee.Authenticate()` and an account, so it cannot run
  unattended here.
