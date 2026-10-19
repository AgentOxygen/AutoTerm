"""Build-time transform, run by Dockerfile.gee-download (deviations 2-5). It derives a Landsat-8-only
download script from GEE/batch_download_direct.py. It never edits that file. Its output is
written to stdout, and every change below is numbered to match the Dockerfile comment.

Usage: python gee-landsat8-patch.py batch_download_direct.py > batch_download_landsat8.py
"""
import re
import sys

src = open(sys.argv[1]).read().split('\n')

l8 = next(i for i, s in enumerate(src) if s.strip() == '#download Landsat-8')
s1 = next(i for i, s in enumerate(src) if 'download Sentinel-1_D' in s)
assert l8 < s1, (l8, s1)

out = src[:l8]
# Deviation 2: uncomment the Landsat-8 block by removing one '# ' level per line. A line that was
# commented twice (`#     # print(fname)`) stays a comment.
for s in src[l8:s1]:
    out.append(re.sub(r'^(\s*)# ?', r'\1', s, count=1) if s.strip().startswith('#') and s.strip() != '#download Landsat-8' else s)

body = '\n'.join(out)
# Deviation 3: LANDSAT/LC08/C01/T1 no longer exists on GEE (ImageCollection.load: "asset not
# found", checked 2026-09-30). LANDSAT/LC08/C02/T1 is its successor: same Tier 1 raw DN, B8 uint16
# at 15 m, and the same LC08_PPPRRR_YYYYMMDD system:index that batch_process_Landsat-8_images.sh parses.
assert body.count("'LANDSAT/LC08/C01/T1'") == 1
body = body.replace("'LANDSAT/LC08/C01/T1'", "'LANDSAT/LC08/C02/T1'")

# Deviation 4: Sentinel blocks (from '###download Sentinel-1_D' to EOF) are dropped. S1/S2 are
# already downloaded, and re-running them could silently add scenes that GEE has since added or
# reprocessed, changing inputs that stage 2 has already consumed.

# Deviation 5: advance the glacier list at the end of the loop. The Zenodo snapshot (cab8265) had
# `line = f.readline()` there. The HEAD rewrite (f1df8ca) dropped it, so `while line:` never ends
# and keeps re-downloading the first glacier.
body = body.rstrip('\n') + '\n    line = download_list.readline()\n'

compile(body, 'batch_download_landsat8.py', 'exec')  # fail the build on any indentation slip
sys.stdout.write(body)
