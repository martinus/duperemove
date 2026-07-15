"""Gated VACUUM: the hashfile is only vacuumed when a prune has left it mostly
free. Ordinary runs must not rewrite it - SQLite reuses freed pages, so the
freelist stays near empty and a full VACUUM would reclaim nothing.
"""

import os
import sqlite3
from harness import DuperemoveTest

# Enough files that the hashfile spans many pages, so pruning most rows frees
# whole pages (SQLite only reclaims a page once it is entirely empty).
N = 3000


class VacuumTest(DuperemoveTest):
    def _populate(self):
        for i in range(N):
            self.mkrand(f"tree/f{i}", 4096)
        self.scan(self.path("tree"))
        self.assertDmOk()

    def _prune_deleted_rows(self):
        """Delete hashfile rows for files no longer on disk (a big prune)."""
        con = sqlite3.connect(self.hf)
        gone = [r[0] for r in con.execute("select id, filename from files")
                if not os.path.exists(r[1])]
        con.executemany("delete from files where id = ?", [(i,) for i in gone])
        con.execute("delete from extents where fileid not in (select id from files)")
        con.execute("delete from blocks where fileid not in (select id from files)")
        con.commit()
        con.close()

    def test_no_vacuum_on_ordinary_rescan(self):
        self._populate()
        size = os.path.getsize(self.hf)
        self.scan(self.path("tree"))          # unchanged -> nothing freed
        self.assertDmOk()
        self.assertEqual(0, self.hf_scalar("PRAGMA freelist_count"))
        self.assertEqual(size, os.path.getsize(self.hf), "no-op rescan must not rewrite")

    def test_vacuum_after_large_prune(self):
        self._populate()
        # remove 90% of the files and prune their rows -> free pages pile up
        for i in range(N * 9 // 10):
            os.remove(self.path(f"tree/f{i}"))
        self._prune_deleted_rows()
        before = os.path.getsize(self.hf)
        self.assertGreater(self.hf_scalar("PRAGMA freelist_count"), 0, "prune should free pages")

        self.scan(self.path("tree"))          # end-of-run vacuum kicks in
        self.assertDmOk()
        self.assertEqual(0, self.hf_scalar("PRAGMA freelist_count"), "vacuum reclaimed free pages")
        self.assertLess(os.path.getsize(self.hf), before, "hashfile shrank")
