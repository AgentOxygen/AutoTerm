#!/bin/sh
set -eu

cd /data

# Respect a user-supplied glacier list already sitting in the mounted output directory; only fall
# back to the baked-in default (GID278/Jakobshavn) when none is present.
if [ ! -f Glacier_ID_list_download_1.txt ]; then
	cp /opt/gee-download/Glacier_ID_list_download_1.txt.default Glacier_ID_list_download_1.txt
fi

exec python "/opt/gee-download/${GEE_SCRIPT:-batch_download_direct.py}"
