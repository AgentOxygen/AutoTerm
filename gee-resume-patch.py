"""Build-time transform, run by Dockerfile.gee-download (deviation 6). It makes the three Sentinel
download blocks of GEE/batch_download_direct.py resumable. It never edits that file. Its output is
written to stdout. Run it on the output of deviation 1 (the `import geetools` line removed).

Each replacement asserts how many times its target occurs, so a changed input fails the build
instead of silently patching something else. The Landsat-8 block is commented out in the input, so
none of the patterns below match it. batch_download_landsat8.py (deviations 2-5) therefore keeps
the original toList() loop.

Usage: python gee-resume-patch.py batch_download_direct.py > batch_download_direct.resumable.py
"""
import sys

body = open(sys.argv[1]).read()


def sub(old, new, count):
    global body
    assert body.count(old) == count, (old, body.count(old), count)
    body = body.replace(old, new)


# A helper listing the scene names already on disk, one directory scan per folder.
sub("import time\n", """import time


def list_existing_fnames(save_folder):
    # One directory scan per folder instead of a glob() per image -
    # turns the skip-check into an O(1) set lookup per image.
    if not os.path.isdir(save_folder):
        return set()
    return {f.rsplit('.', 2)[0] for f in os.listdir(save_folder) if f.endswith('.tif')}
""", 1)

# The count comes from the list of system:index values, which the loop below iterates.
sub("""    count=filteredCollection.size().getInfo()
    print("count is %d"%(count))
    if count==0:
""", """    ids = filteredCollection.aggregate_array('system:index').getInfo()
    print("count is %d"%(len(ids)))
    if len(ids)==0:
""", 3)

sub("        filtered_list=filteredCollection.toList(filteredCollection.size())\n",
    "        existing = list_existing_fnames(save_folder)\n", 3)
sub('Sentinel-1D"%(GID))\n    else:\n\n\n        existing',
    'Sentinel-1D"%(GID))\n    else:\n\n        existing', 1)

# The loop: skip scenes already downloaded, and rebuild each image from its collection ID. The
# added .select() repeats the collection's own .select(), so the pixels fetched are unchanged.
old_loop = """        for i in range(filtered_list.size().getInfo()):
            image=ee.Image(filtered_list.get(i)).clip(geometry)
            fname = image.get('system:id').getInfo().split('/')[-1]
            # print(fname)
"""
new_loop = """        for fname in ids:
            if fname in existing:
                print("skipping %%s (already downloaded)"%%fname)
                continue
            image = ee.Image(%s+'/'+fname).select(%s).clip(geometry)
"""
assert body.count(old_loop) == 3
# In file order: Sentinel-1_D, Sentinel-1_A, Sentinel-2.
for product, bands in [("product", "'HH'"), ("product", "'HH'"), ("data_product", "sel_bands")]:
    body = body.replace(old_loop, new_loop % (product, bands), 1)

compile(body, 'batch_download_direct.py', 'exec')  # fail the build on any indentation slip
sys.stdout.write(body)
