#!/usr/bin/env python3
"""Builds a static Stremio/Nuvio live-TV addon from an M3U playlist.

Probes every channel, keeps the ones that answer, merges duplicate channels
(same name after cleanup) into one tile with several sources, and writes the
addon as plain JSON files into OUT_DIR, ready for any static host.

Usage: build.py OUT_DIR [M3U_URL]
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.request
from pathlib import Path

M3U = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/playlist.m3u"
ID = "bdtv"
# First keyword hit wins; anything unmatched lands in "Other".
GENRES = [
    ("Sports", ("sport", "cricket", "football", "live event")),
    ("News", ("news",)),
    ("Kids", ("kid", "cartoon")),
    ("Music", ("music",)),
    ("Radio", ("radio",)),
    ("Hindi", ("hindi", "india")),
    ("English", ("english",)),
    ("Bangla", ("bangla", "bangladesh", "bdix", "latest", "akash")),
]
VLC = {"http-user-agent": "User-Agent", "http-referrer": "Referer", "http-origin": "Origin"}


def parse(text):
    chans, cur = [], {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            attr = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
            cur = {"name": line.rsplit(",", 1)[-1].strip(), "group": attr.get("group-title", ""),
                   "logo": attr.get("tvg-logo", ""), "headers": {}}
        elif line.startswith("#EXTVLCOPT:") and "=" in line:
            k, v = line[11:].split("=", 1)
            if k in VLC:
                cur.setdefault("headers", {})[VLC[k]] = v
        elif line and not line.startswith("#") and cur.get("name"):
            chans.append({**cur, "url": line})
            cur = {}
    return chans


def alive(ch):
    req = urllib.request.Request(ch["url"], headers={"User-Agent": "Mozilla/5.0", **ch["headers"]})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def clean(name):
    name = re.sub(r"^\[[^\]]*\]\s*", "", name)          # "[BD] Zee Bangla"
    name = re.sub(r"(\s*\(\d+\))+\s*$", "", name)        # "T Sports (3) (3) (3)"
    return re.sub(r"\s+", " ", name).strip()


def genre(group):
    g = group.lower()
    return next((name for name, keys in GENRES if any(k in g for k in keys)), "Other")


def build(chans):
    """Merges live channels by cleaned name -> {slug: meta-with-streams}."""
    metas = {}
    for ch in chans:
        name = clean(ch["name"])
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            continue
        m = metas.setdefault(slug, {"id": f"{ID}:{slug}", "type": "tv", "name": name, "poster": ch["logo"],
                                    "posterShape": "square", "genres": [genre(ch["group"])], "streams": []})
        m["poster"] = m["poster"] or ch["logo"]
        if ch["url"] not in (s["url"] for s in m["streams"]):
            s = {"url": ch["url"], "name": "BD Live TV", "title": f"{name} · source {len(m['streams']) + 1}",
                 "behaviorHints": {"notWebReady": True}}
            if ch["headers"]:
                s["behaviorHints"]["proxyHeaders"] = {"request": ch["headers"]}
            m["streams"].append(s)
    return metas


def write(out, metas):
    def put(path, obj):
        p = out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    genres = sorted({m["genres"][0] for m in metas.values()}, key=lambda g: [n for n, _ in GENRES + [("Other", ())]].index(g))
    items = sorted(metas.values(), key=lambda m: (genres.index(m["genres"][0]), m["name"].lower()))
    previews = [{k: m[k] for k in ("id", "type", "name", "poster", "posterShape", "genres")} for m in items]
    put("manifest.json", {
        "id": "community.bdlivetv", "version": "1.0.0", "name": "BD Live TV",
        "description": f"{len(items)} live Bangladeshi and Indian channels (Mrgify BDIX playlist, dead channels removed).",
        "types": ["tv"], "idPrefixes": [f"{ID}:"], "resources": ["catalog", "meta", "stream"],
        "catalogs": [{"type": "tv", "id": ID, "name": "BD Live TV",
                      "extra": [{"name": "genre", "options": genres, "isRequired": False}]}],
    })
    put(f"catalog/tv/{ID}.json", {"metas": previews})
    for g in genres:
        put(f"catalog/tv/{ID}/genre={g}.json", {"metas": [p for p in previews if p["genres"][0] == g]})
    for m in items:
        put(f"meta/tv/{m['id']}.json", {"meta": {k: v for k, v in m.items() if k != "streams"}})
        put(f"stream/tv/{m['id']}.json", {"streams": m["streams"]})
    return len(items)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    text = urllib.request.urlopen(sys.argv[2] if len(sys.argv) > 2 else M3U, timeout=30).read().decode("utf-8", "replace")
    chans = parse(text)
    with cf.ThreadPoolExecutor(48) as ex:
        live = [c for c, ok in zip(chans, ex.map(alive, chans)) if ok]
    n = write(out, build(live))
    print(f"{len(chans)} channels, {len(live)} alive, {n} after merging duplicates")
    assert n > 20, "suspiciously few live channels; refusing to publish"
