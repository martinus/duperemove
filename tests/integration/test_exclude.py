"""Exclude patterns: literal paths and globs are skipped during listing."""

from harness import DuperemoveTest


class ExcludeTest(DuperemoveTest):
    def test_exclude_literal_path(self):
        self.mkrand("tree/keep", 8000)
        self.mkrand("tree/drop", 8000)
        self.scan(self.path("tree"), "--exclude=" + self.path("tree/drop"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "excluded file not recorded")
        self.assertEqual(
            0, self.hf_scalar("select count(*) from files where filename like '%/drop'"),
            "the dropped path is absent")
        self.assertEqual(
            1, self.hf_scalar("select count(*) from files where filename like '%/keep'"),
            "the kept path is present")

    def test_exclude_glob(self):
        self.mkrand("tree/a.log", 4000)
        self.mkrand("tree/b.log", 4000)
        self.mkrand("tree/c.txt", 4000)
        self.scan(self.path("tree"), "--exclude=" + self.path("tree/*.log"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "only the non-.log file survives")
        self.assertEqual(
            1, self.hf_scalar("select count(*) from files where filename like '%.txt'"),
            "the .txt file is kept")

    def test_exclude_subtree(self):
        self.mkrand("tree/top", 4000)
        self.mkrand("tree/skip/x", 4000)
        self.mkrand("tree/skip/y", 4000)
        self.scan(self.path("tree"), "--exclude=" + self.path("tree/skip/*"))
        self.assertDmOk()
        self.assertEqual(1, self.hf_count("files"), "subtree contents excluded")
