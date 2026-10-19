# AutoTerm output viewer: a self-contained, read-only web view of the stage 2/3 data directory.
# Everything it serves is inside the image (Leaflet is vendored in static/leaflet/), so the page
# works with no internet access. See README.md.
#
#   docker build -t autoterm-viewer tools/data_viewer
#   docker run --rm -p 127.0.0.1:8080:8080 \
#     -v "$PWD/tier-c/data:/data:ro" \
#     -v "$PWD/downloads/Termini.zip:/published/Termini.zip:ro" \
#     autoterm-viewer
#   open http://localhost:8080
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

# Pure-Python GeoTIFF reading (tifffile) instead of GDAL: stage 2 writes simple north-up EPSG:4326
# GeoTIFFs, and this keeps the image free of system libraries.
RUN pip install --no-cache-dir tifffile==2026.9.20 pyshp==3.1.6 pillow==12.3.0 numpy==2.3.5

COPY app.py /app/app.py
COPY static/ /app/static/

# Unprivileged, and the mounts are read-only: the viewer cannot change the data it shows.
RUN useradd --system --uid 10001 viewer
USER viewer
ENV DATA_DIR=/data TERMINI_ZIP=/published/Termini.zip PORT=8080
EXPOSE 8080
CMD ["python", "/app/app.py"]
