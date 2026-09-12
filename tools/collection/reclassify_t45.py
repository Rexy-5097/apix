"""Re-date the T+45 gap-fill batch once the capture date is confirmed.

The five 27-Oct observations were supplied as chat images, so their capture date
could not be read from file metadata. They are loaded under 2026-09-13 (lead
time 44, inadmissible) because that is the conservative reading: mislabelling a
T+44 quote as T+45 would corrupt a frozen bucket, while the reverse only costs
a bucket that this script restores.

Run ONLY if the collector confirms the session ran on 2026-09-12.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "collection" / "collection.sqlite3"
OLD, NEW = "2026-09-13", "2026-09-12"


def main() -> int:
    if "--confirm" not in sys.argv:
        print(__doc__)
        print("Refusing to run without --confirm.")
        return 1
    c = sqlite3.connect(DB)
    n = c.execute(
        "SELECT COUNT(*) FROM canonical_observation WHERE collection_date=?", (OLD,)
    ).fetchone()[0]
    if not n:
        print(f"no observations dated {OLD}; nothing to do")
        return 0
    with c:
        for t in ("collection_run", "collection_attempt", "canonical_observation"):
            c.execute(f"UPDATE {t} SET collection_date=? WHERE collection_date=?", (NEW, OLD))
        c.execute(
            "UPDATE collection_run SET notes = notes || ' | RECLASSIFIED to 2026-09-12 on "
            "collector confirmation; lead time 45, admissible under A.3' WHERE collection_date=?",
            (NEW,),
        )
    print(f"re-dated {n} observations {OLD} -> {NEW}; lead time 44 -> 45 (T+45, admissible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
