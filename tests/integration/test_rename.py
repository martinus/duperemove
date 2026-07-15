"""Rename detection: a moved file keeps its identity, not re-hashed as new."""

import os
from harness import DuperemoveTest


class RenameTest(DuperemoveTest):
    def test_rename_updates_path_not_rows(self):
        self.mkrand("tree/a", 40000)
        self.scan(self.path("tree"))
        digest_before = self.hf_scalar("select quote(digest) from files")
        ino_before = self.hf_scalar("select ino from files")

        os.rename(self.path("tree/a"), self.path("tree/renamed"))
        self.scan(self.path("tree"))
        self.assertDmOk()

        self.assertEqual(1, self.hf_count("files"), "rename must not create a second row")
        self.assertEqual(
            1, self.hf_scalar("select count(*) from files where filename like '%/renamed'"),
            "path updated to the new name")
        self.assertEqual(ino_before, self.hf_scalar("select ino from files"),
                         "same inode after rename")
        self.assertEqual(digest_before, self.hf_scalar("select quote(digest) from files"),
                         "content digest unchanged by a pure rename")

    def test_rename_into_subdir(self):
        self.mkrand("tree/a", 20000)
        self.scan(self.path("tree"))
        os.rename(self.path("tree/a"), self.path("tree/sub/a"))
        self.scan(self.path("tree"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "moved file stays a single row")
        self.assertEqual(
            1, self.hf_scalar("select count(*) from files where filename like '%/sub/a'"),
            "path reflects the new location")
