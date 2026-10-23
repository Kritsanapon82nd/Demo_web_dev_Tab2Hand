#!/usr/bin/env python3
"""Upload songs that the local converter already made (the viewer's `library/` folder) to the deployed site.

    python tools/import_library.py --site https://demo-web-dev-tab2hand.onrender.com --library "C:\\path\\to\\viewer_copy\\library"
Options: --user NAME (default: asks), --only TEXT (only songs whose title contains TEXT), --dry-run.
Needs an admin account. Standard library only. Songs already on the site (same title and track) are skipped.
"""
import argparse, base64, getpass, json, sys, urllib.error, urllib.request
from pathlib import Path


def call(site, path, method="GET", body=None, token=None):
    req = urllib.request.Request(site.rstrip("/") + "/api" + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail", "")
        except Exception:
            detail = ""
        raise SystemExit(f"{method} {path} -> HTTP {e.code} {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--library", required=True)
    ap.add_argument("--user")
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = []
    for d in sorted(Path(a.library).iterdir()) if Path(a.library).is_dir() else []:
        info_p, poses_p = d / "info.json", d / "poses.json"
        if not (info_p.is_file() and poses_p.is_file()):
            continue
        info = json.loads(info_p.read_text(encoding="utf-8"))
        tab = d / str(info.get("file", ""))
        if not tab.is_file():
            cands = [p for p in d.iterdir() if p.suffix.lower() in (".gp3", ".gp4", ".gp5")]
            tab = cands[0] if cands else None
        if tab is None:
            print("skip (no tab file):", d.name)
            continue
        title = info.get("title") or Path(info.get("file", d.name)).stem
        if a.only.lower() in title.lower():
            items.append((d, info, title, tab, poses_p))
    print(f"{len(items)} song(s) found in {a.library}")
    if a.dry_run or not items:
        for _, info, title, tab, _ in items:
            print(f"  {title} | track {info.get('track')} {info.get('trackName', '')} | {tab.name}")
        return

    user = a.user or input("Admin username: ")
    tok = call(a.site, "/login", "POST", {"username": user, "password": getpass.getpass("Password: ")})["access_token"]
    have = set()
    page = 1
    while True:
        r = call(a.site, f"/songs?page={page}&page_size=100")
        have |= {(s["title"], s.get("track")) for s in r["items"]}
        if page * r["page_size"] >= r["total"]:
            break
        page += 1
    for d, info, title, tab, poses_p in items:
        track = int(info.get("track") or 0)
        if (title, track) in have:
            print("already there:", title)
            continue
        body = {"title": title[:200], "note": "imported from local library", "poses": json.loads(poses_p.read_text(encoding="utf-8")),
                "tab_b64": base64.b64encode(tab.read_bytes()).decode(), "tab_name": tab.name, "track": track,
                "track_name": str(info.get("trackName") or "")[:100]}
        r = call(a.site, "/songs", "POST", body, tok)
        print(f"uploaded: {title} (track {track}, {r['num_keyframes']} keyframes)")
    call(a.site, "/logout", "POST", None, tok)


if __name__ == "__main__":
    main()
