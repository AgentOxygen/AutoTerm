#!/bin/bash
# Stage 2, run before batch_read_box_process.sh, inside autoterm-preprocess (Dockerfile.preprocess,
# deviation 2). Writes GID<n>/para.ini with the same lines, in the same order, and from the same
# helpers as batch_read_box_process.sh, except for which Landsat-8 image the size is read from.
# The driver then finds para.ini, skips writing its own, and runs batch_process.sh with these values.
#
# Why: the driver reads x_size_L/y_size_L from the first original_image file (`find | head -n 1`).
# For GID278 that is LC08_007012_20130429.B8.tif, a 172x417 clip of a scene that only grazes the
# ROI, so every Landsat-8 scene would be warped to ~83 m pixels and then upsampled 6x. The published
# GID278 Landsat8 traces have a median vertex spacing of 8.1 m, which matches a 980x1248 grid
# upsampled 2x (8.1 m predicted) and not the 172x417 one (15.3 m). The same check on Sentinel
# (1469x1872, 10.8 m predicted and measured) validates the method. 980x1248 is the most common
# original_image size (261 of 604 scenes), the full footprint of the EPSG:32622 path/rows.
set -u
n=${1:-278}
path=/home/staff/enze/data1/Greenland_front_Mapping/data
cd $path
para=$path/GID$n/para.ini
if [ -f $para ]; then
	echo "$para exists, refusing to overwrite" >&2
	exit 1
fi

# The one change: the Landsat-8 image is the first, in the driver's own find order, whose size is
# the most common size among all Landsat-8 originals.
L_dir=$path/GID$n/GID_${n}_Landsat-8/original_image
sizes=$(for f in `find $L_dir/*.tif`; do echo "$(python $path/get_imagesize.py --image $f) $f"; done)
mode=$(echo "$sizes" | cut -d ' ' -f 1,2 | sort | uniq -c | sort -k1,1nr | head -n 1 | awk '{print $2" "$3}')
L_image=$(echo "$sizes" | awk -v m="$mode" '$1" "$2==m {print $3; exit}')
echo "Landsat-8 size mode: $mode ($(echo "$sizes" | grep -c "^$mode ") of $(echo "$sizes" | wc -l) scenes), from $L_image"
echo "driver would have used: $(echo "$sizes" | head -n 1)"

# Below: batch_read_box_process.sh's own lines.
read xmin ymin xmax ymax <<<$(python $path/get_roi.py --id $n)
read x_size_L y_size_L <<<$(python $path/get_imagesize.py --image $L_image)
S_image=(`find $path/GID$n/GID_${n}_Sentinel-2/original_image/*.tif | head -n 1`)
read x_size_S y_size_S <<<$(python $path/get_imagesize.py --image $S_image)
echo "GID=GID$n" >> $para
echo "GID2=GID_$n" >> $para
echo "xmin=$xmin" >> $para
echo "ymin=$ymin" >> $para
echo "xmax=$xmax" >> $para
echo "ymax=$ymax" >> $para
echo "x_size_L=$x_size_L" >> $para
echo "y_size_L=$y_size_L" >> $para
echo "x_size_S=$x_size_S" >> $para
echo "y_size_S=$y_size_S" >> $para
cat $para
