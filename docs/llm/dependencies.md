# Dependencies

Nothing in this repository declares its dependencies. `pyproject.toml` has an empty `dependencies`
list and the root `Dockerfile` is zero bytes. The lists below were derived by scanning imports and
shell commands.

`Dockerfile.frontdl3` is the only working, verified installation in the repository. Read it before
constructing an environment by hand.

## Python packages

| Import name | Install name | Used by |
|---|---|---|
| `torch` | torch | `pytorch-deeplab-xception/`: train, inference, models, datasets |
| `torchvision` | torchvision | `pytorch-deeplab-xception/` datasets and transforms |
| `numpy` | numpy | Every stage |
| `scipy` | scipy | `data_processing/polygon_complexity.py`, vendored dataloaders |
| `matplotlib` | matplotlib | `data_processing/plot_hist.py`; `truncate_termini.py` uses `matplotlib.path` |
| `pandas` | pandas | `merge_shp/merge_shapefile.py` |
| `geopandas` | geopandas | `merge_shp/merge_shapefile.py` |
| `shapely` | shapely | `data_processing/` area, length, and intersection scripts |
| `pyproj` | pyproj | `data_processing/`, for polar stereographic reprojection |
| `shapefile` | pyshp | `data_processing/calculate_area*.py` |
| `rasterio` | rasterio | `pytorch-deeplab-xception/datasetRS*.py` and `inference*.py` |
| `osgeo` | GDAL Python bindings | `pytorch-deeplab-xception/basic_src/`, `data_processing/`, `gdal_merge_average.py` |
| `intersect` | intersect | `data_processing/truncate_termini*.py`, `get_intersection.py` |
| `ee` | earthengine-api | `GEE/` |
| `geetools` | geetools | `GEE/batch_download.py`, for export to Google Drive |
| `requests` | requests | `GEE/batch_download_direct.py` |
| `PIL` | Pillow | Vendored dataloaders and transforms |
| `imageio` | imageio | `batch_preprocess_images/remove_partial_images.py` |
| `tqdm` | tqdm | `pytorch-deeplab-xception/train.py`, `test.py` |
| `tensorboardX` | tensorboardX | `pytorch-deeplab-xception/utils/summaries.py` |
| `pathos` | pathos | `pytorch-deeplab-xception/datasetRS_MP.py`, for multiprocess patch loading |

Present but not used by AutoTerm:

| Import name | Install name | Only used by |
|---|---|---|
| `pycocotools` | pycocotools | The vendored COCO dataloader inherited from upstream |
| `aggdraw` | aggdraw | `basic_src/test_aggdraw.py` |

Python 2 only imports that remain in the tree and will fail on Python 3:

| Import | File |
|---|---|
| `commands` | `pytorch-deeplab-xception/basic_src/basic.py` |
| `HTMLParser` | `pytorch-deeplab-xception/basic_src/DemConvert.py` |

## System and command line tools

| Tool | Commands invoked |
|---|---|
| GDAL command line | `gdalwarp`, `gdal_translate`, `gdal_merge.py`, `gdal_calc.py`, `gdal_polygonize.py`, `ogr2ogr` |
| GMT, version 6 or later, modern mode | `gmt psxy`, `gmt pstext`, `gmt psbasemap`, `gmt psconvert`, `gmt grdimage`, `gmt gmt2kml`, `gmt gmtset` |
| bash and coreutils | `find`, `split`, `sed`, `awk`, `cut`, `ls`, `tee` |
| `python2` | 13 call sites, all of the form `python2 parameters.py -p para.ini <key>`. The script itself is Python 3 clean, so a symlink to `python3` satisfies this |
| CUDA | `export CUDA_VISIBLE_DEVICES=...`. The root `inference.py` requires a GPU; the submodule fork does not |
| `gdal_contrast_stretch` | Histogram normalization. From the dans-gdal-scripts package, named in the upstream FrontDL3 README |

The GDAL command line tools and the `osgeo` Python bindings must belong to the same Python
interpreter as `torch`. `gdal_merge_average.py` does `from osgeo import gdal` and `inference.py`
does `import torch`, and `exe_inference.sh` calls both through the same `python`. Splitting them
across two environments breaks the inference stage. Using a GDAL base image is the reliable way to
satisfy this.

## Version constraints that matter

| Constraint | Reason |
|---|---|
| PyTorch 2.7 or later for sm_120 GPUs | No earlier wheel has kernels for that architecture |
| `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` with PyTorch 2.6 or later | `torch.load` defaults to `weights_only=True`, which rejects the 2022 checkpoint |
| scipy 1.3 or later requires a source fix | `scipy.ndimage.imread` was removed. The import in `datasetRS_Mar15.py` is unused and can be deleted |
| Python 3.14 requires `--workers 0` | `inference.py` has no `__main__` guard, so a forkserver dataloader worker re-executes it |
| GMT 6 or later | The scripts use modern mode syntax |

`pyproject.toml` declares `requires-python = ">=3.10"`, while the upstream FrontDL3 README describes
a Python 3.6 conda environment. The container build uses the system Python of a current Ubuntu
image.

## External accounts and services

| Requirement | Used by |
|---|---|
| Google Earth Engine account, through `ee.Authenticate()` | All of `GEE/` |
| Google Drive | `GEE/batch_download.py`, for images above the 35 MB direct download limit |

## External data assets

None are in git. Most are now in `downloads/`, which is untracked.

| Asset | Example | Size |
|---|---|---|
| Trained checkpoint | `drn54_May5_2022_0.001_batch16_keep_augmentation.tar` | 326 MB. **Obtained**, at `downloads/` |
| Bedrock and ice mask polygons | `bed_GID<n>_??.gmt`, derived from GrIMP and buffered | **Still missing everywhere.** Expected at `/home/staff/enze/data1/ice_mask/GIMP/crop_bed/buffer_15`. `downloads/Icemask.zip` is a possible derivation source |
| Per-glacier cutting polygons | `GID_<n>_cutting_polygon.gmt` | Only single-glacier samples on disk |
| Flowlines | Per glacier | Per glacier |
| Per-glacier configuration | `para.ini`, `para_upsample.ini` | Per glacier |
| Uncertainty table | `uncertainty_all_lola.txt` | In `merge_shp/`. Readable form at `downloads/uncertainty_all.csv` |
| Training dataset | TermPicks-derived polygon labels | **Obtained**, `downloads/label_shape_TermPicks.zip`, 132,650 files |
| Reference polygons for label generation | Per glacier | **Obtained**, `downloads/reference_polygon_new_ID.zip`, 3,748 files |
| Published terminus traces | `GID<n>.shp` for 295 glaciers | **Obtained**, `downloads/Termini.zip`. The accuracy reference |
| Published ice masks | `GimpMask_15m_2015_{2018,2019,2020}_compress.tif` | **Obtained**, `downloads/Icemask.zip` |
| Glacier identification and ROIs | 295 glaciers | **Obtained**, `downloads/Glacier Identification.csv` |

The published code and data archives are cited in the paper.

| Archive | Status |
|---|---|
| Code, doi:10.5281/zenodo.8270875 | Obtained, at `downloads/AutoTerm.zip`, and checked against the working tree. Contains no missing script and no data asset. It is a snapshot of this repository at commit `cab8265` |
| Data, doi:10.5281/zenodo.7782039 | The data products are now in `downloads/`: termini, ice masks, TermPicks labels, reference polygons, time series, and both CSVs. They do **not** include bedrock polygons, cutting polygons, flowlines, or source imagery |

The paper also states the data were submitted to NSIDC and were pending approval at publication, so
an NSIDC release may supersede the Zenodo data archive.
