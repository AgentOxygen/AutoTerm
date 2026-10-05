# Reproduction plan and complexity assessment

Phase 1 is reproducing the original pipeline in a container. This document assesses how hard that
is, what is already solved, and what actually blocks it.

Revised after the author's working directory and the published data products arrived in
`downloads/`. Most software obstacles are now closed.

## Status update, 2026-10-05

This plan was written before Tier C. What has changed since (details in `IMPLEMENTATION_PLAN.md`):

- **The bedrock polygons are not a blocker for GID278.** The published traces were never truncated at
  the fjord walls, and with `intersect.py` vendored, `truncate_termini.py` passes traces through when no
  polygon exists. Screening then runs normally. The sections below about deriving polygons are
  superseded for GID278.
- Stage 1 (all four sensors) and stage 2 are done for GID278. `Dockerfile.stage3` runs the full
  stage 3 driver; the CPU smoke test passed every step, and the full GPU run is next.
- The "missing helper" scripts Tier B reported were a `PATH` problem, not missing files.
- Open question for C4: the production logs used the `Mar8_2022` checkpoint, not `May5_2022`.

## Headline

**The container is the easy part. One data asset and one data source remain.**

Every script on a live code path is now available. The deployment layout is available as a worked
example rather than a prose description. The published output for all 295 glaciers is available as
an accuracy reference. Two gaps remain, and only one of them is hard.

## What changed with the latest downloads

| Previously blocked | Now |
|---|---|
| Five scripts missing everywhere | Three recovered from `downloads/enze/Front_DL3/`. The two still missing are both on commented-out call sites |
| `batch_plot_truncate_MC_dropout.sh` blocked stage 4 plotting | Recovered. No live code path is missing a script |
| Deployment layout described only in prose | The author's real layout is in `downloads/enze/Front_DL3/` |
| No way to verify pipeline output | `downloads/Termini.zip` holds the published traces for 295 glaciers |
| Trained checkpoint absent | Obtained and verified |
| Glacier ROIs scattered and inconsistent | `downloads/Glacier Identification.csv` gives 295 glaciers with ROI boxes |
| Uncertainty table only in an opaque text file | `downloads/uncertainty_all.csv` gives the readable form |

## What is still missing

| Gap | Severity | Why |
|---|---|---|
| Bedrock polygons `bed_GID<n>_??.gmt` | **Hard blocker for truncation and screening** | Not in any archive. Confirmed absent from the author's directory too |
| Source satellite imagery for a Greenland glacier | Moderate, and solvable | The author's directory holds only one training sample and Alaska intermediates. Images must be re-downloaded from GEE |

Everything else needed for stage 3 is now on disk.

## The bedrock polygons still gate truncation and screening

`batch_truncate_termini.sh` hardcodes:

```
bed_path=/home/staff/enze/data1/ice_mask/GIMP/crop_bed/buffer_15
```

and calls `truncate_termini.py --bed $bed_path/bed_GID${GID}_??.gmt`. A search across every archive
in `downloads/`, including the author's own 12 GB working directory, returns zero matches.

Why this matters more than it appears: screening runs on truncation output.
`batch_smoothness_truncate.sh` opens with `if [ -d $path/$dir/truncate_termini/$temp ]`. With no
bedrock polygons:

1. Truncation produces nothing.
2. Every screening step is skipped.
3. **No error is raised.** The condition is false and the loop moves on.

A container missing this asset runs clean, exits 0, and produces no screened traces.

### `Icemask.zip` is a plausible source

`downloads/Icemask.zip` holds `GimpMask_15m_2015_{2018,2019,2020}_compress.tif`, the published
updated masks. Per section 4.3 of the paper these encode ocean, bedrock, and ice as distinct values,
and per section 3.7 **the bedrock mask is static**, so the bedrock component of any of the three
years is the same bedrock the truncation step expects.

Deriving `bed_GID<n>_??.gmt` from these means: extract the bedrock class, crop per glacier using the
ROI from `Glacier Identification.csv`, buffer, and vectorize to GMT ASCII. The path name says
`buffer_15`, so the buffer is probably 15 units, but that is an inference from a directory name.

This is a real deviation and must be labelled as one. The derived polygons are ours, not the
author's, so traces truncated with them are not strictly reference output. It is, however, far
better grounded than deriving from the public GrIMP release, because this is the author's own mask.

Prefer asking the authors for the original files first. That is the only zero-deviation route.

## Source imagery is a solved problem, just not a free one

Stage 1 can re-download from Google Earth Engine, and `Glacier Identification.csv` supplies ROI
bounding boxes for all 295 glaciers, which is exactly the input `GEE/batch_download_direct.py`
needs. Requirements: a Google Earth Engine account, `ee.Authenticate()`, and network policy
allowing it.

Note that sensor selection in that script is a manual comment-and-uncomment toggle, and that
downloaded images then need stage 2 preprocessing before inference. See `pitfalls.md`.

## The hardcoded paths remain the easiest part

76 references across 45 files collapse to **two roots**:

| Root | References | Now satisfiable from |
|---|---|---|
| `/home/staff/enze/Front_DL3/` | 59 | `downloads/enze/Front_DL3/`, mounted directly |
| `/home/staff/enze/data1/` | 17 | Assembled from the archives, except the ice mask subtree |

Mounting `downloads/enze/Front_DL3` at `/home/staff/enze/Front_DL3` satisfies 59 of the 76
references with no edits and no layout assembly, because it is already the layout the scripts
expect. This is now the single highest-leverage decision in the reproduction.

Do not rewrite paths. Mount them.

## Verification is now possible

This is the most important change. `downloads/Termini.zip` contains complete shapefile sets for all
295 glaciers, the published 278,239 traces.

A reproduction run can now be checked properly:

1. Run the pipeline for glacier `n`.
2. Compare the output traces against `Termini/GID<n>.shp`, matching on the `Date` and `Satellite`
   attributes.
3. Measure the deviation using the paper's own metric: enclosed area between the two traces divided
   by trace length, giving metres. `data_processing/calculate_error.py` already implements it.

The paper's own figures give the scale to expect: 79 m test error before screening, 62 m after, and
37 m average duplicate-trace uncertainty. A reproduction landing far outside that range indicates a
problem.

This also supplies the phase 2 baseline directly. AutoTerm v2 can be measured against the same
shapefiles.

## Recommended tiers

### Tier A: confirm the container with the real checkpoint

Run `Dockerfile.frontdl3` with the checkpoint in `downloads/`. Compare against the recorded result
of 28 patches and one 814-point trace for Jakobshavn Isbrae.

Effort: hours. Risk: low. Do this first regardless of anything else.

### Tier B: stage 3 driver against the author's mounted directory

Mount `downloads/enze/Front_DL3` at `/home/staff/enze/Front_DL3`, add the container environment from
`Dockerfile.frontdl3`, and run `batch_inference_plot_mv_figure_dir.sh` for one glacier using sample
imagery.

Effort: roughly one day, down from one to three. The layout assembly step is gone. Risk: moderate,
mostly in the silent failure modes. Truncation and screening will still no-op, and that must be
stated explicitly rather than read as success.

### Tier C: real imagery, truncation, and screening

Needs the bedrock polygons resolved and a population of images for one glacier from GEE.

Effort: one to two weeks. Risk: concentrated entirely in the bedrock polygon decision. Value: this
is the tier that actually demonstrates AutoTerm rather than FrontDL3.

Split it in practice:

| Step | Depends on |
|---|---|
| C1. Download and preprocess one glacier's images | GEE account and network access |
| C2. Obtain or derive bedrock polygons | Author response, or the `Icemask.zip` derivation |
| C3. Run truncation and screening | C1 and C2 |
| C4. Compare against `Termini/GID<n>.shp` | C3 |

### Tier D: MC dropout, merge, and figures

Now unblocked on the script side. `batch_plot_truncate_MC_dropout.sh` was the last missing live
dependency and is available. Uses `uncertainty_all.csv` for the merge stage.

Effort: additional days. Risk: moderate.

## Suggested sequencing

1. Run Tier A now. Cheap, validates the checkpoint and environment together.
2. **Ask the authors for the bedrock polygons.** This is the long pole and the only zero-deviation
   route. Do it in parallel with everything else.
3. Build Tier B against the mounted author directory.
4. Start C1, the GEE download, since it is independent of the bedrock question.
5. Decide on the `Icemask.zip` derivation only if the authors do not respond.

## Verification discipline

The dominant failure mode is silence, not error. Verify by checking that expected output files exist
and are non-empty, never by checking exit codes. Now that `Termini.zip` exists, also verify
numerically against the published traces rather than settling for "it produced something".
`running-and-verifying.md` lists the specific failure modes that exit 0.
