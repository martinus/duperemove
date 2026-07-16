"""Files rewritten between scan and dedupe must be skipped, not EINVAL.

A dedupe request that reaches past a destination's current EOF (the file
shrank), or whose unaligned length no longer ends exactly at EOF (the file
grew), makes the kernel fail that destination with EINVAL. duperemove now
detects the size change up front, skips the member as "changed since scan",
and still dedupes the unchanged members. Requires a reflink-capable fs.
"""

import os
from harness import DuperemoveTest, requires_reflink


@requires_reflink
class ChangedSinceScanTest(DuperemoveTest):
    SIZE = 19389        # deliberately unaligned, like a fuzz-corpus input

    def _mkgroup(self, names):
        data = os.urandom(self.SIZE)
        return [self.write(f"tree/{n}", data) for n in names]

    def test_shrunk_and_grown_dests_are_skipped(self):
        a, b, c, d = self._mkgroup("abcd")
        self.sync()

        # scan only, then change two files behind the hashfile's back
        self.dm("-r", self.path("tree"))
        self.assertDmOk()
        os.truncate(b, 12000)
        with open(c, "ab") as f:
            f.write(b"grown")
        self.sync()

        # dedupe purely from the (now stale) hashfile
        self.dm("-d", f"--read-hashes={self.hf}", hashfile=False)
        self.assertDmOk()
        self.assertNotIn("Invalid argument", self.out,
                         "size-changed dests must not reach the kernel")
        self.sync()

        # the unchanged pair still got deduped, the changed ones intact
        self.assertShared(a, d, "unchanged members still dedupe")
        self.assertEqual(os.path.getsize(b), 12000)
        self.assertEqual(os.path.getsize(c), self.SIZE + 5)
