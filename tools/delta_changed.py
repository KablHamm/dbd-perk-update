"""Did the rebuild actually change the delta?

    python tools/delta_changed.py <published.json> <rebuilt.json>

Exit 0 when the perk list and the wiki totals are unchanged, 1 when they are
not. The `built` timestamp moves on every run and is deliberately not part of
the answer - otherwise every daily run would look like a change and the commit
would be noise. Says what moved either way, so the run log and the commit
message read the same way.
"""
import io
import json
import sys


def load(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def keys(doc):
    """The same identity the app merges on: side plus lower-cased name."""
    return {(p.get("k"), (p.get("n") or "").strip().lower())
            for p in (doc or {}).get("perks", [])}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    before, after = load(sys.argv[1]), load(sys.argv[2])

    if before is None:
        print("no usable delta published yet - this run is the first")
        return 1
    if after is None:
        raise SystemExit("the rebuilt delta is unreadable: %s" % sys.argv[2])

    was, now = keys(before), keys(after)
    added = sorted(now - was)
    dropped = sorted(was - now)
    totals_same = before.get("wikiTotals") == after.get("wikiTotals")

    if not added and not dropped and totals_same:
        print("unchanged: %d perk(s) in the delta" % len(now))
        return 0

    for kind, name in added:
        print("  + [%s] %s" % (kind, name))
    for kind, name in dropped:
        print("  - [%s] %s" % (kind, name))
    if not totals_same:
        print("  wiki totals %s -> %s" % (
            json.dumps(before.get("wikiTotals")),
            json.dumps(after.get("wikiTotals"))))
    print("changed: %d perk(s) in the delta" % len(now))
    return 1


if __name__ == "__main__":
    sys.exit(main())