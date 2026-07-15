"""Scan phase: hashfile creation, per-file/per-extent digests, determinism."""

import os
from harness import DuperemoveTest


class ScanTest(DuperemoveTest):
    def test_records_every_file(self):
        self.mkrand("tree/a", 20000)
        self.mkrand("tree/sub/b", 30000)
        self.mkrand("tree/sub/c", 4096)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(3, self.hf_count("files"), "one row per regular file")
        self.assertEqual(
            0, self.hf_scalar("select count(*) from files where digest is null"),
            "every file digested")
        self.assertGreater(self.hf_count("extents"), 0, "extents recorded")

    def test_duplicates_share_digest(self):
        self.mkdup("tree/a", "tree/b", 65536)
        self.mkrand("tree/c", 65536)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(
            2, self.hf_scalar("select count(distinct digest) from files"),
            "two distinct digests for {a==b, c}")
        da = self.hf_scalar("select quote(digest) from files where filename like '%/a'")
        db = self.hf_scalar("select quote(digest) from files where filename like '%/b'")
        self.assertEqual(da, db, "identical files share a digest")

    def test_distinct_content_distinct_digest(self):
        self.mkrand("tree/a", 40000)
        self.mkrand("tree/b", 40000)
        self.scan(self.path("tree"))
        self.assertDmOk()
        da = self.hf_scalar("select quote(digest) from files where filename like '%/a'")
        db = self.hf_scalar("select quote(digest) from files where filename like '%/b'")
        self.assertNotEqual(da, db, "distinct content must hash differently")

    def test_scan_is_deterministic(self):
        self.mkrand("tree/a", 50000)
        self.mkdup("tree/x", "tree/y", 30000)
        self.scan(self.path("tree"))
        fp, ep = self.files_fingerprint(), self.extents_fingerprint()
        os.remove(self.hf)
        self.scan(self.path("tree"))
        self.assertEqual(fp, self.files_fingerprint(), "files table reproducible")
        self.assertEqual(ep, self.extents_fingerprint(), "extents table reproducible")

    def test_empty_tree(self):
        os.makedirs(self.path("tree"), exist_ok=True)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(0, self.hf_count("files"), "empty tree -> no files")

    def test_single_file_argument(self):
        self.mkrand("a", 12345)
        self.scan(self.path("a"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "single-file scan records one row")
