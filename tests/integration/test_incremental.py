"""Incremental rescan: reusing a hashfile across runs."""

import os
from harness import DuperemoveTest


class IncrementalTest(DuperemoveTest):
    def test_rescan_unchanged_is_stable(self):
        self.mkrand("tree/a", 40000)
        self.mkdup("tree/x", "tree/y", 20000)
        self.scan(self.path("tree"))
        self.assertDmOk()
        fp, ep = self.files_fingerprint(), self.extents_fingerprint()
        self.scan(self.path("tree"))                 # second run, same hashfile
        self.assertDmOk()
        self.assertEqual(fp, self.files_fingerprint(), "unchanged rescan keeps files")
        self.assertEqual(ep, self.extents_fingerprint(), "unchanged rescan keeps extents")

    def test_rescan_picks_up_changed_content(self):
        self.mkrand("tree/a", 40000)
        self.scan(self.path("tree"))
        before = self.hf_scalar("select quote(digest) from files where filename like '%/a'")
        self.mkrand("tree/a", 40000)                 # rewrite with new content
        os.utime(self.path("tree/a"), (1893456000, 1893456000))  # bump mtime
        self.scan(self.path("tree"))
        self.assertDmOk()
        after = self.hf_scalar("select quote(digest) from files where filename like '%/a'")
        self.assertNotEqual(before, after, "changed content -> new digest")
        self.assertEqual(1, self.hf_count("files"), "still one row for the file")

    def test_rescan_adds_new_file(self):
        self.mkrand("tree/a", 10000)
        self.scan(self.path("tree"))
        self.assertEqual(1, self.hf_count("files"))
        self.mkrand("tree/b", 10000)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(2, self.hf_count("files"), "new file added on rescan")

    def test_rescan_prunes_deleted_file(self):
        # A file deleted from disk is pruned from the hashfile automatically on
        # the next scan (its row plus the cascaded extent/block hashes), so a
        # stale hashfile does not keep growing.
        self.mkrand("tree/a", 10000)
        self.mkrand("tree/b", 10000)
        self.scan(self.path("tree"))
        self.assertEqual(2, self.hf_count("files"))
        os.remove(self.path("tree/b"))
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "deleted file's row pruned")
        self.assertEqual(
            0, self.hf_scalar("select count(*) from files where filename like '%/b'"),
            "the deleted file's row is gone")
        self.assertEqual(
            0, self.hf_scalar("select count(*) from extents "
                              "where fileid not in (select id from files)"),
            "no orphaned extent hashes left behind")

    def test_prune_is_stat_based_not_scope_based(self):
        # Pruning is stat-based: scanning only a subdirectory must NOT drop the
        # rows of files elsewhere in the hashfile that still exist on disk. A
        # "delete everything I didn't walk" prune would wrongly nuke them.
        self.mkrand("tree/keep/a", 10000)
        self.mkrand("tree/other/b", 10000)
        self.scan(self.path("tree"))
        self.assertEqual(2, self.hf_count("files"))
        self.scan(self.path("tree/keep"))           # only part of the tree
        self.assertDmOk()
        self.assertEqual(2, self.hf_count("files"),
                         "out-of-scope but still-existing file retained")

    def test_rescan_prunes_null_digest_rows(self):
        # The NULL-digest prune does fire: a stale half-scanned row is cleaned up.
        self.mkrand("tree/a", 10000)
        self.scan(self.path("tree"))
        ghost = self.path("tree/ghost")
        with __import__("sqlite3").connect(self.hf) as con:
            cols = [r[1] for r in con.execute("pragma table_info(files)")]
            # Newer schemas carry a NOT NULL path_hash; a real interrupted scan
            # sets it at insert time (only the digest is filled in later).
            extra_c = ", path_hash" if "path_hash" in cols else ""
            extra_v = ", 987654321" if "path_hash" in cols else ""
            con.execute(
                "insert into files (filename, ino, subvol, size, mtime, dedupe_seq, "
                f"digest, flags{extra_c}) values (?, 999999, 0, 123, 0, 0, NULL, 0{extra_v})",
                (ghost,))
        self.assertEqual(2, self.hf_count("files"), "stale row inserted")
        self.scan(self.path("tree"))                 # prune runs before scanning
        self.assertDmOk()
        self.assertEqual(
            0, self.hf_scalar("select count(*) from files where filename like '%/ghost'"),
            "NULL-digest stale row pruned")
