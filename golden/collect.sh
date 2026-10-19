#!/usr/bin/env bash
# Copy the comparable outputs of a stage 3 run into a clean tree.
# usage: collect.sh <data dir containing GID278/> <dest dir>
# Kept: per-sensor in_polygon_gmt and truncate_termini traces (including abandon/), the final
# GID278/truncate_termini traces (including merge_two/) and the time series text.
# Left out: figures, .invert files, gmt.history/gmt.conf/temp.txt (GMT bookkeeping), logs.
set -euo pipefail
src=${1:?usage: collect.sh <data dir> <dest>}
dest=${2:?usage: collect.sh <data dir> <dest>}
[ -d "$src/GID278" ] || { echo "no $src/GID278" >&2; exit 1; }
mkdir -p "$dest"; dest=$(cd "$dest" && pwd)
( cd "$src/GID278" && find . \( -path '*/in_polygon_gmt/*' -o -path '*/truncate_termini/*' \) -type f \
	\( -name '*.gmt' -o -name 'GID278_all.txt' -o -name 'area_change_1.txt' \) \
	-not -path './truncate_termini/*/duplicate/*' | LC_ALL=C sort \
	| while read -r f; do mkdir -p "$dest/$(dirname "$f")"; cp "$f" "$dest/$f"; done )
n=$(find "$dest" -type f | wc -l)
[ "$n" -gt 0 ] || { echo "collected nothing from $src" >&2; exit 1; }
