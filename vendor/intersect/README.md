# Vendored: `intersect.py`

`data_processing/truncate_termini.py` does `from intersect import intersection` and unpacks two
values, `lo, la = intersection(...)`. The module is not in this repository, the `FrontDL3/`
submodule, the author's directory (`downloads/enze/Front_DL3/`), or the Zenodo code archive.
Without it, truncation fails on import for every trace, and the failure is silent at the exit-code
level (IMPLEMENTATION_PLAN.md, Tier B, B4).

| | |
|---|---|
| Upstream | https://github.com/sukhbinder/intersection |
| File | `intersect/intersect.py`, verbatim |
| Pinned commit | `cbf072fc1a` (2020-04-04), "Added pip installer and fixed issue of overlapping lines" |
| License | MIT, `LICENSE` in this directory, taken from the same commit |
| sha256 | `ee26d563bec6bf35ac2fba254744121bcaa2745e457fc1f96dd774fd005230c6` |

The user approved vendoring this module on 2026-09-30. Nothing in the author's material names
the source.

## Why this exact commit

The call site constrains the choice to one upstream revision. Upstream history of the file:

| Revision | Module name | `intersection()` returns | Compatible with `from intersect import intersection` + `lo, la = ...` |
|---|---|---|---|
| 2017 (`372d55752d` and earlier) | `intersection.py` | `x, y` | No, wrong module name |
| `6ea7c8dae2` (2020-04-04) | `intersection/intersection.py` | `x, y` | No, wrong module name |
| **`cbf072fc1a` (2020-04-04)** | **`intersect/intersect.py`** | **`x, y`** | **Yes, the only one** |
| `50bbb4e64d` (2020-12-20) onward, every PyPI release | `intersect/intersect.py` | `x, y, i, j` | No, `ValueError: too many values to unpack` |

So the author's copy was `cbf072fc1a` or a local copy of it. This was checked by fetching each
revision on 2026-09-30. The first vendoring attempt used `50bbb4e64d`, and a unpack test caught
the four-value return.

## Known incompatibility

Line 90 uses `np.Inf`, which NumPy 2.0 removed. It sits in the `except` branch for singular
segment pairs, so the breakage only shows when two segments are parallel. Environments with
NumPy ≥ 2 need a one-token `sed` (`np.Inf` → `np.inf`), identical to upstream's own later fix
`bb1348ba14`. Apply it as a numbered deviation in the Dockerfile that installs this file. Never
edit the file here, so that this copy stays byte-identical to upstream.

Verified on 2026-09-30 in the `frontdl3-cpu` image (NumPy 2.3.5), with the `sed` applied:
`sin(x) = 0.5` on [0, 10] gives x = 0.5265, 2.6161, 6.8097, 8.8982 (analytic: 0.5236, 2.6180, 6.8068,
8.9012; the difference is linear interpolation on 50 samples), unpacked as two values.

## How it is used

The stage 3 image copies this file next to `truncate_termini.py` (Python puts the script's
directory on `sys.path`). The copy is logged as a numbered deviation in that Dockerfile. This
supplies a missing dependency and does not change the original source.
