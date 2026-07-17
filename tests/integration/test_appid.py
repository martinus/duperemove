"""The hashfile is branded with a SQLite application_id ("oans") so oans owns
its own format: it stamps its own files and strictly refuses any hashfile that
does not carry the brand (a foreign program's, or a pre-brand/duperemove one),
recreating it fresh.
"""

import sqlite3
import subprocess
from harness import DuperemoveTest, DUPEREMOVE

OANS_APP_ID = 0x6F616E73  # ascii "oans"


def app_id(path):
    # Note: sqlite3's context manager commits but does NOT close, and a lingering
    # connection holds a WAL lock that breaks oans's unlink+recreate. Close it.
    con = sqlite3.connect(path)
    try:
        return con.execute("PRAGMA application_id").fetchone()[0]
    finally:
        con.close()


def set_app_id(path, value):
    con = sqlite3.connect(path)
    try:
        con.execute(f"PRAGMA application_id = {value}")
        con.commit()
    finally:
        con.close()


class AppIdTest(DuperemoveTest):
    def test_fresh_hashfile_is_branded(self):
        self.mkrand("tree/a", 8000)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(OANS_APP_ID, app_id(self.hf), "fresh hashfile carries the oans brand")

    def test_unbranded_is_refused_and_rebuilt(self):
        # A file without the brand (application_id 0: a pre-brand oans file or a
        # duperemove one) is strictly refused and recreated fresh.
        self.mkrand("tree/a", 8000)
        self.mkrand("tree/b", 8000)
        self.scan(self.path("tree"))
        set_app_id(self.hf, 0)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertIn("Recreating", self.out, "unbranded hashfile rebuilt")
        self.assertEqual(OANS_APP_ID, app_id(self.hf), "recreated as an oans file")

    def test_foreign_application_is_refused(self):
        # A hashfile branded by some other program is refused and recreated.
        self.mkrand("tree/a", 8000)
        self.mkrand("tree/b", 8000)
        self.scan(self.path("tree"))
        set_app_id(self.hf, 0x12345678)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertIn("Recreating", self.out, "foreign hashfile rebuilt")
        self.assertEqual(OANS_APP_ID, app_id(self.hf), "rebuilt as an oans file")

    def test_rebuild_is_compacted(self):
        # A from-scratch build is written at insert density, so oans VACUUMs it
        # once at the end. Run non-quiet (the message is suppressed by -q) after
        # forcing a rebuild and check the compaction fired.
        self.mkrand("tree/a", 8000)
        self.scan(self.path("tree"))
        set_app_id(self.hf, 0x12345678)  # force a rebuild on the next run
        proc = subprocess.run(
            [DUPEREMOVE, "-r", "--hashfile", self.hf, self.path("tree")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertIn("Recreating", proc.stdout)
        self.assertIn("Compacting", proc.stdout, "rebuilt hashfile is VACUUMed")
        self.assertEqual(0, sqlite3.connect(self.hf).execute(
            "PRAGMA freelist_count").fetchone()[0], "no free pages after compaction")
