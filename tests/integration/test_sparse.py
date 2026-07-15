"""Sparse files, holes, unaligned tails, and empty/zero files."""

import os
from harness import DuperemoveTest


class SparseTest(DuperemoveTest):
    def test_sparse_file_scans(self):
        self.make_sparse("tree/sp", os.urandom(65536), 131072, os.urandom(40000))
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"))
        self.assertGreater(self.hf_count("extents"), 0, "sparse file has recorded extents")

    def test_sparse_identical_same_digest(self):
        head, tail = os.urandom(65536), os.urandom(40000)
        self.make_sparse("tree/a", head, 131072, tail)
        self.make_sparse("tree/b", head, 131072, tail)   # identical, independent
        self.scan(self.path("tree"))
        self.assertDmOk()
        da = self.hf_scalar("select quote(digest) from files where filename like '%/a'")
        db = self.hf_scalar("select quote(digest) from files where filename like '%/b'")
        self.assertEqual(da, db, "identical sparse files share a digest")

    def test_empty_files(self):
        self.write("tree/empty1", b"")
        self.write("tree/empty2", b"")
        self.mkrand("tree/data", 8000)
        self.scan(self.path("tree"))
        self.assertDmOk()
        # Whether empty files get a row is a policy detail; the invariant that
        # matters is a clean run with the non-empty file recorded.
        self.assertEqual(
            1, self.hf_scalar("select count(*) from files where filename like '%/data'"),
            "non-empty file recorded")

    def test_unaligned_sizes(self):
        self.mkrand("tree/a", 131072 + 1)
        self.mkrand("tree/b", 262144 + 4095)
        self.mkrand("tree/c", 1)
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(3, self.hf_count("files"), "unaligned files all recorded")
        self.assertEqual(
            0, self.hf_scalar("select count(*) from files where digest is null"),
            "unaligned files all digested")
