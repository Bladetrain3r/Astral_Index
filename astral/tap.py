"""Polite TAP client. One query at a time, a pause between queries, bounded retries,
and every response kept as a gzipped snapshot with a manifest line (url, query, time, and
the sha256 of the stored file, so `sha256sum` checks it).

A query already in the manifest for the same archive is read from disk, never re-fetched.
"""
import csv, gzip, hashlib, io, json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone

ARCHIVES = {
    "gaia": "https://gea.esac.esa.int/tap-server/tap",
    "euclid": "https://eas.esac.esa.int/tap-server/tap",
}
PAUSE_S = 3.0          # between live queries, per process
RETRIES = 3
TIMEOUT_S = 300
USER_AGENT = "astral-index/0.1 (catalogue cross-check; polite; one connection)"

_last_call = [0.0]


class TapError(RuntimeError):
    pass


def _key(archive, query):
    return hashlib.sha256((archive + "\n" + " ".join(query.split())).encode()).hexdigest()[:16]


def _manifest_path(snap_dir):
    return os.path.join(snap_dir, "MANIFEST.jsonl")


def _manifest(snap_dir):
    out = {}
    p = _manifest_path(snap_dir)
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    out[r["key"]] = r
    return out


def _parse(text):
    return list(csv.DictReader(io.StringIO(text)))


def _fetch(archive, query):
    wait = PAUSE_S - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    data = urllib.parse.urlencode(
        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query}).encode()
    req = urllib.request.Request(ARCHIVES[archive] + "/sync", data=data,
                                 headers={"User-Agent": USER_AGENT})
    err = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read().decode("utf-8")
            _last_call[0] = time.time()
            if body.lstrip().startswith("<"):   # the archives answer errors as VOTable XML
                raise TapError("archive rejected the query: " + body[:400])
            return body
        except TapError:
            raise
        except Exception as e:                  # network or 5xx: back off and retry
            err = e
            _last_call[0] = time.time()
            time.sleep(PAUSE_S * (2 ** (attempt + 1)))
    raise TapError(f"{archive}: gave up after {RETRIES} tries: {err}")


def query(archive, adql, snap_dir, label, offline=False):
    """Return rows (list of dicts, all values strings). Snapshot and manifest on first fetch."""
    adql = " ".join(adql.split())
    key = _key(archive, adql)
    man = _manifest(snap_dir)
    if key in man:
        path = os.path.join(snap_dir, man[key]["file"])
        with open(path, "rb") as f:
            stored = f.read()
        if hashlib.sha256(stored).hexdigest() != man[key]["sha256"]:
            raise TapError(f"snapshot {path} does not match its manifest hash")
        return _parse(gzip.decompress(stored).decode("utf-8"))
    if offline:
        raise TapError(f"offline and no snapshot for {label} ({key})")
    body = _fetch(archive, adql)
    stored = gzip.compress(body.encode("utf-8"), mtime=0)        # mtime=0: stable bytes
    os.makedirs(snap_dir, exist_ok=True)
    fname = f"{label}.{key}.csv.gz"
    with open(os.path.join(snap_dir, fname), "wb") as f:
        f.write(stored)
    rec = {"key": key, "archive": archive, "url": ARCHIVES[archive] + "/sync", "label": label,
           "query": adql, "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "rows": len(_parse(body)), "sha256": hashlib.sha256(stored).hexdigest(), "file": fname}
    with open(_manifest_path(snap_dir), "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return _parse(body)
