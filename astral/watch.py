"""Watch both archives for a change of release. Cheap: a handful of metadata queries.

    python -m astral.watch            compare with data/watch/state.json, print a report
    python -m astral.watch --accept   record what the archives show now as the known state

It never reruns anything. A change is reported; a person decides on the rerun (GATES.md, G6).
Exit code 0: no change. 3: something changed (the report is also written to watch_report.md).
"""
import argparse, hashlib, html, json, os, re, sys, urllib.request
from . import tap, run

STATE = os.path.join(run.HERE, "data", "watch", "state.json")
QUERIES = {
    "gaia_schemas": ("gaia", "SELECT schema_name FROM tap_schema.schemas"),
    "euclid_schemas": ("euclid", "SELECT schema_name FROM tap_schema.schemas"),
    "euclid_releases": ("euclid", "SELECT release_name, version, purpose FROM dr1.data_release"),
    "euclid_vis_tiles": ("euclid", "SELECT release_name, COUNT(DISTINCT tile_index) AS tiles "
                                   "FROM dr1.mosaic_product WHERE instrument_name='VIS' GROUP BY release_name"),
    "euclid_catalogue_columns": ("euclid", "SELECT column_name FROM tap_schema.columns "
                                           "WHERE table_name='dr1.mer_catalogue_wide_survey'"),
    "gaia_source_columns": ("gaia", "SELECT column_name FROM tap_schema.columns "
                                    "WHERE table_name='gaiadr3.gaia_source'"),
}
PAGES = {
    "euclid_known_issues": "https://euclid.dataspace.esa.int/public-eds-help/DR1_Foundation.html",
}
HASHED = ("euclid_catalogue_columns", "gaia_source_columns")   # long lists: keep a count and a hash


def page_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": tap.USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode("utf-8", "replace")
    t = re.sub(r"(?s)<(script|style).*?</\1>", "", t)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def current():
    out = {}
    for name, (archive, q) in QUERIES.items():
        try:
            rows = sorted(" | ".join(r.values()) for r in tap._parse(tap._fetch(archive, q)))
            out[name] = ({"count": len(rows), "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}
                         if name in HASHED else rows)
        except Exception as e:                       # an unreachable archive is not a release change
            out[name] = {"unreachable": type(e).__name__}
    for name, url in PAGES.items():
        try:
            t = page_text(url)
            out[name] = {"sha256": hashlib.sha256(t.encode()).hexdigest(), "chars": len(t)}
        except Exception as e:
            out[name] = {"unreachable": type(e).__name__}
    return out


def diff(old, new):
    lines = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if a == b or (isinstance(b, dict) and "unreachable" in b):
            continue
        if isinstance(a, list) and isinstance(b, list):
            for x in sorted(set(b) - set(a)):
                lines.append(f"- `{k}`: new `{x}`")
            for x in sorted(set(a) - set(b)):
                lines.append(f"- `{k}`: gone `{x}`")
        else:
            lines.append(f"- `{k}`: was `{json.dumps(a, sort_keys=True)}`, now `{json.dumps(b, sort_keys=True)}`")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept", action="store_true")
    a = ap.parse_args()
    now = current()
    if a.accept:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as fh:
            json.dump(now, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("state recorded")
        return 0
    with open(STATE) as fh:
        old = json.load(fh)
    down = [k for k, v in now.items() if isinstance(v, dict) and "unreachable" in v]
    lines = diff(old, now)
    if down:
        print("unreachable this run (ignored):", ", ".join(down))
    if not lines:
        print("no change")
        return 0
    report = "The archives no longer match `data/watch/state.json`:\n\n" + "\n".join(lines) + \
             "\n\nNothing was rerun. See GATES.md, G6.\n"
    with open(os.path.join(run.HERE, "watch_report.md"), "w") as fh:
        fh.write(report)
    print(report)
    return 3


if __name__ == "__main__":
    sys.exit(main())
