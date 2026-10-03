"""Rebuild perks-update.json for the perk picker.

The perk tables on deadbydaylight.wiki.gg are rendered by a Lua module, so the
only machine-readable form of them is the rendered HTML: slice the page at the
Survivor_Perks / Killer_Perks / History anchors, then read one <tr> per perk
(two <th> cells - icon, name - and one <td> cell, the description).

The file this writes carries only the perks the app does not already bundle,
so a rebuild is safe to run at any time: it never rewrites what is already
there, and nothing is added that the wiki does not list. The app reads it from
a public copy of this repository on raw.githubusercontent.com, because the wiki
sends no CORS header at all and cannot be fetched from the device.

Which perks the app already has comes from baseline.json - the side and name of
every bundled perk, and nothing else, which is a fraction of perks.json's size.
Regenerate it from the app's perks.json whenever the app is rebuilt.

    python tools/build_perk_update.py
"""
import html
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
SRC = "https://deadbydaylight.wiki.gg/wiki/Perks"
TAG = re.compile(r"<[^>]+>")


def clean(s):
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n\n", s)
    s = re.sub(r"(?i)</li>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "", s)
    s = re.sub(r"(?i)</?(td|th|tr|table|div|span|ul|ol|strong|em|b|i|p)[^>]*>", "", s)
    s = TAG.sub("", s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u200e", "").replace("\u200f", "")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def perk_rows(section, kind):
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", section):
        ths = re.findall(r"(?is)<th[^>]*>(.*?)</th>", tr)
        tds = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)
        if len(ths) < 2 or not tds:
            continue  # the table's own header row
        name = clean(ths[1])
        if not name:
            continue
        m = re.search(r'src="(/images/[^"]+)"', ths[0])
        icon = ("https://deadbydaylight.wiki.gg" + html.unescape(m.group(1))) if m else ""
        out.append({"n": name, "d": clean(tds[0]), "i": icon, "k": kind})
    return out


def scrape():
    req = urllib.request.Request(SRC, headers={"User-Agent": "OS3 perk picker data build"})
    raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    i_s = raw.find('id="Survivor_Perks_')
    i_k = raw.find('id="Killer_Perks_')
    i_h = raw.find('id="History"')
    if min(i_s, i_k) < 0:
        raise SystemExit("page layout changed: section anchors not found")
    fresh = perk_rows(raw[i_s:i_k], "S") + perk_rows(raw[i_k:i_h if i_h > i_k else len(raw)], "K")
    if not fresh:
        raise SystemExit("page layout changed: no perk rows parsed")
    return fresh


def load_baseline():
    """The (side, name) pairs the app already bundles, and how many it has.

    baseline.json next to this file is the repository's own copy. A local
    perks.json - the app's full bundle - is read instead when one is present,
    so a checkout sitting next to the app still answers the same question.
    """
    path = os.path.join(APP, "baseline.json")
    if not os.path.exists(path):
        path = os.path.join(APP, "perks.json")
    with io.open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if isinstance(doc, dict) and "keys" in doc:
        return ({(k, (n or "").strip().lower()) for k, n in doc["keys"]},
                doc.get("count", 0))
    return ({(p["k"], (p["n"] or "").strip().lower()) for p in doc}, len(doc))


def main():
    fresh = scrape()
    have, base = load_baseline()
    new = [p for p in fresh
           if (p["k"], p["n"].strip().lower()) not in have and p["i"]]
    gone = sorted(have - {(p["k"], p["n"].strip().lower()) for p in fresh})
    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": SRC,
        "wikiTotals": {"S": sum(1 for p in fresh if p["k"] == "S"),
                       "K": sum(1 for p in fresh if p["k"] == "K")},
        "base": base,
        "perks": new,
    }
    path = os.path.join(APP, "perks-update.json")
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("wiki: %d perks (S=%d K=%d)   bundled: %d   new: %d   %s" % (
        len(fresh), out["wikiTotals"]["S"], out["wikiTotals"]["K"], base, len(new),
        out["built"]))
    for p in new:
        print("  + [%s] %s" % (p["k"], p["n"]))
    if gone:
        print("  ! in the bundle but no longer on the wiki (%d): %s" % (
            len(gone), ", ".join(n for _, n in gone[:20])))
    print("wrote %s (%d bytes)" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()