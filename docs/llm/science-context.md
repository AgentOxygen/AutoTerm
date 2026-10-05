# Science context

Source: `manuscript.md` at the repository root (Zhang, Catania, Trugman, 2023, The Cryosphere 17,
3485-3503, doi:10.5194/tc-17-3485-2023).

This document explains what each pipeline stage is for. Read it when you need to know why code
does something, or whether a value you are about to change is meaningful.

## The problem the pipeline solves

A glacier terminus is the boundary where a glacier meets the ocean. Its position over time is a
primary measurement for studying ice sheet mass loss. Before AutoTerm, terminus positions were
mapped manually, which is slow and produces sparse, inconsistent records.

Roughly 430,000 satellite images of Greenland glaciers exist on Google Earth Engine. Manual mapping
cannot process that volume. AutoTerm automates the full path from image download to a quality
controlled, uncertainty quantified shapefile.

## What "automated" means here

Four things were automated that prior deep learning studies did not automate:

1. Image collection and preprocessing.
2. Quality control, called the screening module. Prior studies either had none or applied it by hand.
3. Uncertainty quantification.
4. Regular delivery of updated data products.

Two things remain manual: preparing the region of interest bounding box for each glacier (done once
per glacier), and checking for mismatches when converting training traces.

## Key numbers from the paper

| Quantity | Value | Where it appears in code |
|---|---|---|
| Glaciers covered | 295 | `GEE/Glacier_ID_list.txt` lists 290 |
| Terminus traces produced | 278,239 | Output, not in repository |
| Source images processed | 433,721 | Output, not in repository |
| Time span | 1984 to 2021 | Date filters in `GEE/batch_download*.py` |
| Test error | 79 m before screening, 62 m after | Computed by `data_processing/calculate_error.py` |
| Success rate | 90 percent on test set, 64 percent overall | Fraction passing the screening module |
| Duplicate trace uncertainty | 37 m average, range 10 to 204 m | `merge_shp/uncertainty_all_lola.txt` |
| Training pairs from TermPicks | 16,440 | Training data, not in repository |
| Additional manual training pairs | 1,466 | Training data, not in repository |
| Upsampling trigger | image width below 1000 pixels | `batch_preprocess_images/batch_upsample.sh` |
| Binary threshold on model output | 0.5 | `batch_inference_termini/exe_inference.sh` |

## Stage by stage purpose

### Data collection

Five satellite missions are used: Landsat 5, Landsat 7, Landsat 8, Sentinel-1, and Sentinel-2.
Sentinel-1 is synthetic aperture radar. It is the only sensor that works in the polar winter, so it
is what makes seasonal analysis possible. It has three known problems: georeferencing offsets
relative to optical sensors, uneven spatial coverage, and speckle noise.

The paper states that no cloud filter is applied at download time. The reason given is that cloud
fraction is computed over the whole satellite scene, but the terminus occupies a small part of it,
so a scene reported as heavily clouded may still show the terminus clearly. Cloud affected results
are meant to be removed later by the screening module instead.

The download scripts in this repository do apply a 60 percent cloud filter. See `pitfalls.md`.

Images are cropped to the region of interest on the Google Earth Engine side, before download. This
reduces a Sentinel-1 scene from about 800 MB to under 10 MB.

### Preprocessing

Two normalizations are applied, both to reduce the variety the model must handle.

Histogram normalization equalizes pixel value ranges between radar and optical images, which have
different dynamic ranges and textures.

Size normalization upsamples small images so that glaciers of very different physical size appear
at similar pixel size to the model. Greenland glaciers range from 1 to 80 km wide. Images narrower
than 1000 pixels are upsampled by an integer factor using cubic interpolation until just over 1000
pixels wide. Large images are never downsampled, to avoid losing spatial information. A second
benefit is that upsampling produces more overlapping patches over the same ground area, so the
model makes more predictions per location.

The paper reports that size normalization reduced test error for all five small glaciers tested.

### Training data

Training labels come from TermPicks (Goliber et al., 2022), a manually digitized dataset of over
39,000 terminus traces for 291 Greenland glaciers, 1916 to 2019.

TermPicks traces are polylines. The model needs binary polygon masks. The conversion works like
this: one reference polygon is drawn by hand per glacier, positioned so its terminus edge sits
up-glacier of every TermPicks trace for that glacier. Each trace therefore crosses the reference
polygon at exactly two points. A label polygon is formed by joining the trace between those two
intersections with the rest of the reference polygon.

Using TermPicks instead of hand-prepared data is the single largest source of accuracy in this
work. The paper reports a direct comparison: training on only the 1,466 hand-prepared examples
gives 315 m test error and 46 percent success rate; training with TermPicks gives 79 m and 90
percent.

Five image conditions were identified as hard, and hand-labelled examples were added for each:
visible terminus under cloud, blurry winter Sentinel-1, shadow over the terminus, tabular icebergs
near the terminus, and ice melange with texture similar to glacier ice.

Augmentation is rotation by 90, 180, and 270 degrees plus flipping, which multiplies the training
set by four.

There is no code in this repository for the TermPicks to polygon conversion.

### Model

DeepLabv3+ (Chen et al., 2018), an encoder-decoder segmentation network with atrous spatial pyramid
pooling. The encoder-decoder half gives sharp object boundaries, which matters because the output
is a boundary. The pyramid pooling half senses multi-scale context, which matters because input
resolutions differ between sensors.

Training configuration reported in the paper:

| Setting | Value |
|---|---|
| Loss | Binary cross entropy |
| Optimizer | Stochastic gradient descent |
| L2 regularization | 5e-4 |
| Learning rate | 2e-3, chosen from 5e-3, 2e-3, 1e-3 by validation loss |
| Batch size | 16 |
| Hardware | Four A100 GPUs, 160 GB total GPU memory |
| Validation split | 5 percent of training data |
| Early stopping | Validation error flat for 3 consecutive epochs |
| Epochs run | 7, about 1 week wall clock |
| Peak memory | 120 GB |
| Test set | 100 randomly selected TermPicks traces |

Inference plus post-processing for one image takes under one minute.

### Error metric

Test error is not a pixel metric. It is the area enclosed between the predicted trace and the
reference trace, divided by the length of the reference trace. The result is a distance in metres.
If the two traces cross, the areas on each side of every crossing are summed.

This definition is why `data_processing/calculate_abs_area.py` and `invert_data2.py` exist: to
close two open polylines into a polygon, one of them must be reversed before concatenation.

### Screening module

The purpose is to discard bad traces automatically. The model will produce output even for images
where no terminus is visible.

The paper defines four metrics:

1. Number of intersections between the trace and the glacier flowline. Keep only traces with
   exactly one intersection.
2. Terminus length.
3. Terminus curvature, computed over every three adjacent points along the trace, then averaged.
4. Area enclosed between a trace and its nearest trace in time, which detects outliers in the
   terminus position time series.

Thresholds come from the interquartile range of the metric across traces for the same glacier:

- Upper threshold: Q3 + 1.5 * (Q3 - Q1)
- Lower threshold: Q1 - 1.5 * (Q3 - Q1)

Length uses both thresholds, because terminus length should not change much in either direction.
Curvature and area change use the upper threshold only, because good traces are expected to be
smooth and to change slowly.

Thresholds are computed from Landsat 8 and Sentinel-2 results only, then applied to all sensors.
The reason is that Sentinel-1 has speckle noise, Landsat 7 has scan line corrector failure, and
Landsat 5 has too few images, so thresholds derived from those sensors would be unreliable.

Removing outliers changes the distribution, so new thresholds are computed and screening repeats.
The paper says up to 10 times, or until no outliers are found.

Large calving events are a real signal that looks like an area change outlier. The rule that
separates them: examine area change over five consecutive traces in a moving time window, and
remove the first large-area trace only if more than one large-area change is present. A genuine
calving event produces exactly one large change.

The code implements this differently from the paper in several respects. See `pitfalls.md`.

### Sentinel-1 georeferencing adjustment

Sentinel-1 has known location errors along the azimuth direction. Because sensors overlap, the same
date sometimes has both a Sentinel-1 trace and an optical trace. The correction computes the area
enclosed between same-date Sentinel-1 and optical traces, averages that difference across all such
pairs, and applies the average as an offset.

### Uncertainty quantification

Two independent methods are used, and they measure different things.

Duplicate trace uncertainty: compare Landsat 8 and Sentinel-2 traces from the same date. The model
is fixed and the input varies, so this measures data uncertainty. Sentinel-1 duplicates are not
used because they are consumed by the georeferencing correction. Landsat 5 and 7 are not used
because they lack same-date overlap with other sensors. This estimate is biased low, because
Landsat 8 and Sentinel-2 are the two highest resolution sensors.

Monte Carlo dropout uncertainty: leave dropout active at inference, run the model several times,
and measure the spread. The input is fixed and the model varies, so this measures model
uncertainty. Sampling is 10 images per sensor, 3 inferences per image, for cost reasons. This
produces one value per sensor.

Each glacier therefore carries six uncertainty values: one from duplicate traces and five from MC
dropout, one per sensor. This is the structure of `merge_shp/uncertainty_all_lola.txt`.

### Ice and ocean masks

New terminus traces are used to update the 2015 GrIMP ice mask (Howat, 2017). Masks are regenerated
annually, not monthly, because glacier area does not change meaningfully month to month. Traces
from the time of minimum ice extent (late autumn) are chosen.

The procedure: vectorize the ocean mask, crop it to the glacier regions of interest, replace those
regions with the new terminus traces, rasterize the result as the new ocean mask. The bedrock mask
is treated as static. The new ice mask is what remains after subtracting the new ocean mask and the
bedrock mask.

Reported net ice extent change: 520 km2 in 2018, 660 km2 in 2019, 72 km2 in 2020.

There is no code in this repository for mask generation.

## Stated limitations

These are the paper's own limitations, useful when judging whether a code change is worth making.

1. Training requires 120 GB of GPU memory and 5 to 7 days.
2. The screening module assumes most results for a glacier are good. If most are bad, the
   interquartile thresholds are computed from bad data and screening fails to remove anything.
3. The model still struggles with the five hard image conditions.
4. Validation outside Greenland has not been done.
5. Duplicate trace uncertainty is biased low.
6. Only imagery available on Google Earth Engine is used. Air photos, ASTER, and other SAR products
   are excluded.

## Stated future work

Relevant because it describes intended features that do not yet exist in code.

1. Update each glacier's region of interest automatically, from the intersection of the glacier
   centerline with the most recent terminus trace.
2. Use low success rate and high uncertainty as an automatic signal that more training data is
   needed for a given glacier.
3. Update glacier ID files when a terminus splits into tributaries or several merge into one.
   Proposed scheme: suffix the existing numeric ID with letters a, b, c for tributaries; on merge,
   keep the ID of the largest tributary.
