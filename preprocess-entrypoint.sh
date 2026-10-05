#!/bin/bash
# Assembles the stage 2 data directory described in AutoTerm Pipeline.docx, Step 2/3, then runs the
# given command. This assembles the environment only: no script is edited, and nothing under /gee
# (the read-only GEE download mount) is written.
set -eu
data=/home/staff/enze/data1/Greenland_front_Mapping/data
cd "$data"

# "Copy get_roi.py get_imagesize.py, remove_partial_images.py into the data directory". The same
# goes for the batch_*.sh drivers, which cd into $data and call their siblings by bare name.
cp -rn /opt/autoterm/batch_preprocess_images/. "$data"/

# Glacier lists read by the drivers. Default to GID278 unless the mount already supplies them.
[ -f Glacier_ID_list_temp.txt ] || echo 278 > Glacier_ID_list_temp.txt
[ -f Glacier_ID_list_all.txt ] || cp Glacier_ID_list_temp.txt Glacier_ID_list_all.txt

# GEE writes <GID>_<Satellite> (GID278_Sentinel-2) but every stage 2 driver reads
# GID<n>/GID_<n>_<Satellite>/original_image. The procedure's "create a folder for each glacier and
# mv the satellite folders into it" step leaves that rename implicit. Symlinks, not copies or moves,
# keep the 25 GB of downloads read-only and in place.
while read -r n; do
	[ -n "$n" ] || continue
	for src in /gee/GID${n}_*/; do
		[ -d "$src" ] || continue
		sat=$(basename "$src"); sat=${sat#GID${n}_}
		dst=$data/GID$n/GID_${n}_$sat/original_image
		if [ ! -d "$dst" ]; then
			mkdir -p "$dst"
			ln -s "$src"*.tif "$dst"/
		fi
	done
done < Glacier_ID_list_temp.txt

# The author's build_folder_structure.sh creates polygon/, hist_eq/, in_polygon_gmt/, figure/, and
# script/. It skips its mv step because original_image/ already exists.
bash /opt/autoterm/build_folder_structure.sh "$data" > /dev/null

exec "$@"
