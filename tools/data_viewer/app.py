"""AutoTerm output viewer: a read-only web view of a stage 2/3 data directory.

Serves one static page (static/index.html) and a small JSON API over the mounted directories. It
never writes to them.

  DATA_DIR      stage 2/3 data directory (default /data): GID<n>/GID_<n>_<sensor>/...
  TERMINI_ZIP   published traces, downloads/Termini.zip, read in place (default /published/Termini.zip)
  PORT          default 8080
"""
import functools
import io
import json
import os
import re
import threading
import zipfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import shapefile
import tifffile
from PIL import Image

DATA_DIR = os.environ.get('DATA_DIR', '/data')
TERMINI_ZIP = os.environ.get('TERMINI_ZIP', '/published/Termini.zip')
PORT = int(os.environ.get('PORT', '8080'))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# Every name that reaches the filesystem is checked against these, so no request can step outside
# the mounted tree.
GID_RE = re.compile(r'^GID\d+$')
SENSOR_RE = re.compile(r'^GID_\d+_[A-Za-z0-9-]+(_[AD])?$')
CKPT_RE = re.compile(r'^[A-Za-z0-9_.-]+$')
NAME_RE = re.compile(r'^(\d{8})_([A-Za-z0-9]+)_GID\d+(?:_[AD])?_stretch$')

# Where a trace sits after a full run decides its status. The GID-level folders are checked first:
# batch_mv_abandon_duplicate.sh also moves area-screened traces into the sensor-level abandon/.
STATUS_ORDER = ['final', 'area_screened', 'duplicate', 'screened', 'no_final', 'no_trace',
                'image_rejected', 'not_run']


def _listdir(path, suffix):
    try:
        return {f[:-len(suffix)] for f in os.listdir(path) if f.endswith(suffix)}
    except (FileNotFoundError, NotADirectoryError):
        return set()


def _subdirs(path):
    try:
        return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))
    except FileNotFoundError:
        return []


def read_gmt(path):
    """GMT ASCII: 'lon lat' per line, '>' starts a new segment, '#' is a comment."""
    segs, cur = [], []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.startswith('>'):
                if cur:
                    segs.append(cur)
                cur = []
                continue
            parts = s.split()
            try:
                cur.append([float(parts[0]), float(parts[1])])
            except (ValueError, IndexError):
                continue
    if cur:
        segs.append(cur)
    return segs


def decimate(seg, max_pts):
    if len(seg) <= max_pts:
        return seg
    step = len(seg) / max_pts
    out = [seg[int(i * step)] for i in range(max_pts)]
    out.append(seg[-1])
    return out


def checkpoints(gid):
    """Checkpoint names: directories under any sensor's in_polygon_gmt/."""
    found = set()
    for s in sensors(gid):
        found.update(_subdirs(os.path.join(DATA_DIR, gid, s, 'in_polygon_gmt')))
    return sorted(c for c in found if CKPT_RE.match(c))


def sensors(gid):
    return [d for d in _subdirs(os.path.join(DATA_DIR, gid)) if SENSOR_RE.match(d)]


def glacier_index(gid, ckpt):
    """One entry per image date, with its stage 3 status for the given checkpoint."""
    g = os.path.join(DATA_DIR, gid)
    top = os.path.join(g, 'truncate_termini', ckpt) if ckpt else None
    final = _listdir(top, '.gmt') if top else set()
    area = _listdir(os.path.join(top, 'abandon'), '.gmt') if top else set()
    dup = _listdir(os.path.join(top, 'duplicate'), '.gmt') if top else set()
    items, counts = [], {}
    for s in sensors(gid):
        sd = os.path.join(g, s)
        ups = _listdir(os.path.join(sd, 'upsample'), '.tif')
        rejected = _listdir(os.path.join(sd, 'hist_eq', 'abandon'), '.tif') - ups
        raw = _listdir(os.path.join(sd, 'in_polygon_gmt', ckpt), '.gmt') if ckpt else set()
        st = os.path.join(sd, 'truncate_termini', ckpt) if ckpt else None
        scr = (_listdir(os.path.join(st, 'abandon'), '.gmt') | _listdir(os.path.join(st, 'duplicate'), '.gmt')) if st else set()
        c = dict.fromkeys(STATUS_ORDER, 0)
        for name in sorted(ups | rejected | raw):
            m = NAME_RE.match(name)
            if not m:
                continue
            if name in rejected:
                status = 'image_rejected'
            elif not ckpt or not os.path.isdir(os.path.join(sd, 'in_polygon_gmt', ckpt)):
                status = 'not_run'
            elif name in final:
                status = 'final'
            elif name in area:
                status = 'area_screened'
            elif name in dup:
                status = 'duplicate'
            elif name in scr:
                status = 'screened'
            elif name in raw:
                status = 'no_final'  # traced, but in neither the final set nor any abandon/duplicate folder
            else:
                status = 'no_trace'
            c[status] += 1
            items.append({'name': name, 'date': m.group(1), 'sat': m.group(2), 'sensor': s,
                          'status': status, 'raw': name in raw})
        c['images'] = len(ups) + len(rejected)
        counts[s] = c
    items.sort(key=lambda x: (x['date'], x['sensor']))
    return items, counts


def trace_path(gid, sensor, ckpt, name, kind):
    g = os.path.join(DATA_DIR, gid)
    if kind == 'raw':
        cands = [os.path.join(g, sensor, 'in_polygon_gmt', ckpt)]
    else:
        st = os.path.join(g, sensor, 'truncate_termini', ckpt)
        top = os.path.join(g, 'truncate_termini', ckpt)
        cands = [top, os.path.join(top, 'abandon'), os.path.join(top, 'duplicate'),
                 st, os.path.join(st, 'abandon'), os.path.join(st, 'duplicate')]
    for d in cands:
        p = os.path.join(d, name + '.gmt')
        if os.path.isfile(p):
            return p
    return None


def image_path(gid, sensor, name):
    sd = os.path.join(DATA_DIR, gid, sensor)
    for sub in ('upsample', 'hist_eq', os.path.join('hist_eq', 'abandon'),
                os.path.join('hist_eq', 'abandon_result_based')):
        p = os.path.join(sd, sub, name + '.tif')
        if os.path.isfile(p):
            return p
    return None


def geotiff_bounds(page, shape):
    """(west, south, east, north) of a north-up GeoTIFF, from ModelPixelScale (33550) and
    ModelTiepoint (33922). Stage 2 writes every image this way (EPSG:4326, no rotation)."""
    scale = page.tags[33550].value
    tie = page.tags[33922].value
    h, w = shape[:2]
    west = tie[3] - tie[0] * scale[0]
    north = tie[4] + tie[1] * scale[1]
    return [west, north - h * scale[1], west + w * scale[0], north]


@functools.lru_cache(maxsize=48)
def render_png(path, mtime):
    """Band 1 as an 8-bit PNG, with nodata (0) transparent. Returns (png bytes, bounds)."""
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        a = page.asarray()
        bounds = geotiff_bounds(page, a.shape)
    if a.ndim == 3:
        a = a[..., 0] if a.shape[-1] <= 4 else a[0]
    if a.dtype != np.uint8:
        valid = a[a > 0]
        lo, hi = (np.percentile(valid, [2, 98]) if valid.size else (0, 1))
        a8 = np.clip((a.astype(np.float64) - lo) / max(hi - lo, 1e-9) * 254 + 1, 1, 255).astype(np.uint8)
        a8[a == 0] = 0
        a = a8
    img = Image.fromarray(np.dstack([a, (a > 0).astype(np.uint8) * 255]), 'LA')
    buf = io.BytesIO()
    img.save(buf, 'PNG', compress_level=1)
    return buf.getvalue(), bounds


_pub_lock = threading.Lock()


@functools.lru_cache(maxsize=16)
def published(gid):
    """Published traces for one glacier from Termini.zip: list of {date, sat, segs}."""
    if not os.path.isfile(TERMINI_ZIP):
        return None
    with _pub_lock, zipfile.ZipFile(TERMINI_ZIP) as z:
        names = {os.path.basename(n): n for n in z.namelist() if not n.startswith('__MACOSX')}
        if gid + '.shp' not in names:
            return []
        parts = {ext: io.BytesIO(z.read(names[gid + '.' + ext])) for ext in ('shp', 'shx', 'dbf')}
    r = shapefile.Reader(shp=parts['shp'], shx=parts['shx'], dbf=parts['dbf'])
    fields = [f[0] for f in r.fields[1:]]
    out = []
    for rec, shp in zip(r.records(), r.shapes()):
        d = dict(zip(fields, rec))
        idx = list(shp.parts) + [len(shp.points)]
        segs = [[list(p) for p in shp.points[idx[i]:idx[i + 1]]] for i in range(len(idx) - 1)]
        out.append({'date': str(d.get('Date', '')).replace('-', '')[:8], 'sat': str(d.get('Satellite', '')),
                    'segs': segs})
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC_DIR, **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=HTTPStatus.OK):
        body = json.dumps(obj, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=HTTPStatus.BAD_REQUEST):
        self._json({'error': msg}, status)

    def do_GET(self):
        u = urlparse(self.path)
        if not u.path.startswith('/api/'):
            return super().do_GET()
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        gid, sensor, ckpt, name = q.get('gid', ''), q.get('sensor', ''), q.get('ckpt', ''), q.get('name', '')
        if gid and not GID_RE.match(gid):
            return self._err('bad gid')
        if sensor and not SENSOR_RE.match(sensor):
            return self._err('bad sensor')
        if ckpt and not CKPT_RE.match(ckpt):
            return self._err('bad checkpoint')
        if name and not NAME_RE.match(name):
            return self._err('bad name')
        try:
            route = u.path[len('/api/'):]
            if route == 'glaciers':
                return self._json({'glaciers': [d for d in _subdirs(DATA_DIR) if GID_RE.match(d)],
                                   'published': os.path.isfile(TERMINI_ZIP)})
            if route == 'glacier':
                ck = checkpoints(gid)
                if ckpt and ckpt not in ck:
                    return self._err('unknown checkpoint', HTTPStatus.NOT_FOUND)
                use = ckpt or (ck[0] if ck else '')
                items, counts = glacier_index(gid, use)
                poly = os.path.join(DATA_DIR, gid, 'polygon')
                cut = sorted(f for f in _listdir(poly, '.gmt') if 'cutting_polygon' in f)
                return self._json({'gid': gid, 'checkpoints': ck, 'checkpoint': use, 'sensors': sensors(gid),
                                   'items': items, 'counts': counts,
                                   'cutting': [{'name': c, 'segs': read_gmt(os.path.join(poly, c + '.gmt'))} for c in cut]})
            if route == 'image':
                p = image_path(gid, sensor, name)
                if not p:
                    return self._err('no image', HTTPStatus.NOT_FOUND)
                png, bounds = render_png(p, os.path.getmtime(p))
                if q.get('meta'):
                    return self._json({'bounds': bounds})
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(png)))
                self.send_header('Cache-Control', 'max-age=3600')
                self.end_headers()
                self.wfile.write(png)
                return
            if route == 'trace':
                kind = q.get('kind', 'final')
                p = trace_path(gid, sensor, ckpt, name, kind)
                if not p:
                    return self._json({'segs': [], 'path': None})
                return self._json({'segs': read_gmt(p), 'path': os.path.relpath(p, DATA_DIR)})
            if route == 'published':
                pub = published(gid)
                if pub is None:
                    return self._json({'available': False, 'traces': []})
                date, sat = q.get('date'), q.get('sat')
                if date:
                    sel = [t for t in pub if t['date'] == date and (not sat or t['sat'] == sat)]
                    return self._json({'available': True, 'traces': sel})
                return self._json({'available': True, 'traces': [
                    {'date': t['date'], 'sat': t['sat'], 'segs': [decimate(s, 300) for s in t['segs']]} for t in pub]})
            if route == 'overview':
                items, _ = glacier_index(gid, ckpt)
                feats = []
                for it in items:
                    if it['status'] != 'final':
                        continue
                    p = trace_path(gid, it['sensor'], ckpt, it['name'], 'final')
                    if p:
                        feats.append({'date': it['date'], 'sensor': it['sensor'], 'name': it['name'],
                                      'segs': [decimate(s, 300) for s in read_gmt(p)]})
                return self._json({'traces': feats})
            return self._err('unknown endpoint', HTTPStatus.NOT_FOUND)
        except Exception as e:  # report, don't kill the server
            return self._err('%s: %s' % (type(e).__name__, e), HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == '__main__':
    print('AutoTerm viewer on port %d, data %s, published %s (%s)'
          % (PORT, DATA_DIR, TERMINI_ZIP, 'found' if os.path.isfile(TERMINI_ZIP) else 'not mounted'), flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
