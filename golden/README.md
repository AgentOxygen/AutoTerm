# Golden reference outputs (GID278, checkpoint `drn54_May5_2022_0.001_batch16_keep_augmentation`)

The smallest reproducible case for AutoTerm: a fixed set of stage 2 images (`upsample/*.tif`) run
through the unmodified stage 3 driver (`batch_inference_plot_mv_figure_dir.sh`), with every
comparable output stored here. A candidate (the pinned images on CPU or GPU, an Apptainer build, or
v2 once it can write the same layout) passes when its outputs are **byte-identical**.

| Tier | Inputs | Files | What it exercises |
|---|---|---|---|
| `golden-8` | 2 images per sensor (`tier-c/smoke-script`) | 32 | every driver step, fast (about 21 min on CPU, under 2 min on the 5070) |
| `golden-24` | 6 images per sensor (`tier-c/smoke`) | 86 | the above plus screening: 6 traces abandoned by the per-sensor smoothness screen (S1-A 5, S1-D 1), 18 merged dates |

The final time-series screen abandons nothing in either tier. That needs the full run.

Kept per run (`collect.sh`): per-sensor `in_polygon_gmt/` and `truncate_termini/` traces (with
`abandon/`), the final `GID278/truncate_termini/` traces (with `merge_two/`), and the time-series text.
Left out: figures, `.invert` files, and GMT bookkeeping (`gmt.history`, `gmt.conf`, `temp.txt`).

`inputs-<tier>.sha256` pins the input images and cutting polygon (stage 2 output, not committed: too
large). Check them with `cd <data>/GID278 && sha256sum -c golden/inputs-24.sha256`.

## Reference producer

The CPU run of the pinned `autoterm-stage3` image (torch 2.14.0, GDAL 3.13.3 base). The 5070 with
`NVIDIA_TF32_OVERRIDE=0` reproduced `golden-24` exactly (2026-10-19). With TF32 on, some points move
by one pixel (7.31 m at most), so keep it off for a byte-exact check. A different architecture or
framework will not be byte-identical: compare traces with the enclosed-area/length metric instead
(the 36 m median against the published traces is the ceiling, not the goal).

## Run

```bash
./gpu-smoke.sh 8      # or 24; runs on the host GPU, then verifies (run from the repo root)
golden/verify-golden.sh 24 <data dir of any run>     # verify alone
```

Refresh the golden set only with a deliberate decision: it is the measuring instrument.
