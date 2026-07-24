"""A file whose absolute path exceeds PATH_MAX is skipped with a warning, not
silently ignored, and the rest of the scan proceeds normally (issue #108).

PATH_MAX bounds the path any syscall (statx/open/the dedupe ioctl) accepts, so
oans cannot hash a file it can only name with a longer absolute path. The
kernel *filesystem* allows such paths though - a deep enough directory chain
built with relative chdir()s reaches names longer than PATH_MAX. oans must warn
about each one it skips (so the omission is visible) while still hashing and
deduplicating every in-range file it walks past.
"""

import os

from harness import DuperemoveTest, requires_reflink

# The kernel PATH_MAX on Linux; a single path component maxes out at NAME_MAX
# (255). Chaining 255-char directories steps the absolute path in ~256-byte
# jumps, so a handful of levels clears 4096.
PATH_MAX = 4096
NAME_MAX = 255


class LongPathTest(DuperemoveTest):
    def _build_over_pathmax_file(self):
        """Create, under a deep chain of max-length directories, one file whose
        absolute path exceeds PATH_MAX. Returns (top_dir, victim_basename).

        The chain is built with incremental chdir()s because the leaf's own
        absolute path is too long to pass to mkdir()/open() directly.
        """
        top = self.path("deep")           # short, in-range root to point oans at
        os.makedirs(top, exist_ok=True)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)    # never leave the test in the deep tree
        os.chdir(top)

        comp = "d" * NAME_MAX
        cur_len = len(top)
        # Descend while the *directory* path stays in range (each level adds the
        # separator + 255 chars). Stop one short so a 255-char filename here
        # tips just over PATH_MAX.
        while cur_len + 1 + NAME_MAX <= PATH_MAX:
            os.mkdir(comp)
            os.chdir(comp)
            cur_len += 1 + NAME_MAX

        victim = "v" * NAME_MAX           # cur_len + 1 + 255 > PATH_MAX
        assert cur_len + 1 + len(victim) > PATH_MAX, "victim path not over PATH_MAX"
        with open(victim, "wb") as f:
            f.write(b"over-the-limit contents\n")
        os.chdir(cwd)
        return top, victim

    @requires_reflink
    def test_long_path_reported_not_silently_skipped(self):
        top, victim = self._build_over_pathmax_file()
        self.scan(top)

        # The core of issue #108: the skip is announced, not silent.
        self.assertIn("exceeds PATH_MAX", self.out,
                      "over-PATH_MAX path must be reported, not silently dropped")
        # And the un-hashable file is genuinely absent from the hashfile.
        recorded = self.hf_scalar(
            "select count(*) from files where filename like ?",
            (f"%{victim}",))
        self.assertEqual(0, recorded,
                         "a file past PATH_MAX cannot be hashed, so it is not stored")

    @requires_reflink
    def test_scan_continues_past_long_path(self):
        # A deep, un-hashable branch must not derail the rest of the run: an
        # ordinary duplicate pair sitting beside it still deduplicates.
        self._build_over_pathmax_file()
        a, b = self.mkdup("pair/a.bin", "pair/b.bin", 128 * 1024)
        self.sync()

        self.dedupe(self.work)
        self.assertDmOk()
        self.assertIn("exceeds PATH_MAX", self.out)
        self.sync()
        self.assertShared(a, b,
                          "in-range duplicates dedupe despite an over-PATH_MAX sibling")
