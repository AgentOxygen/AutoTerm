#!/bin/bash
# Stage 2a for one Sentinel-only glacier (default GID278), inside autoterm-preprocess. This does the
# work of batch_read_box_process.sh past its Landsat-8 gate (Dockerfile.preprocess, deviation 1),
# writing para.ini with the same lines and helper commands that script uses, minus the Landsat
# sizes. It then runs the author's batch_remove_partial_images.sh unchanged.
set -u
n=${1:-278}
path=/home/staff/enze/data1/Greenland_front_Mapping/data
cd $path
para=$path/GID$n/para.ini
read xmin ymin xmax ymax <<<$(python $path/get_roi.py --id $n)
S_image=(`find $path/GID$n/GID_${n}_Sentinel-2/original_image/*.tif | head -n 1`)
read x_size_S y_size_S <<<$(python $path/get_imagesize.py --image $S_image)
if [ ! -f $para ]; then
	echo "GID=GID$n" >> $para
	echo "GID2=GID_$n" >> $para
	echo "xmin=$xmin" >> $para
	echo "ymin=$ymin" >> $para
	echo "xmax=$xmax" >> $para
	echo "ymax=$ymax" >> $para
	echo "x_size_S=$x_size_S" >> $para
	echo "y_size_S=$y_size_S" >> $para
fi
echo "bash batch_process_sentinel.sh $n $xmin $ymin $xmax $ymax - - $x_size_S $y_size_S"
bash batch_process_sentinel.sh $n $xmin $ymin $xmax $ymax - - $x_size_S $y_size_S
bash batch_remove_partial_images.sh
