"""Dedupe should skip destinations that already share the target's extents.

Upstream #331: deduping snapshots re-issues FIDEDUPERANGE on extents that are
already shared, forcing the kernel to re-read/compare gigabytes for no change.
The fix skips a destination whose physical extent map already matches the
target. The critical safety property is the converse: genuinely independent
(un-shared) copies must still be deduped. Requires a reflink-capable fs.
"""

import os
import subprocess
from harness import DuperemoveTest, requires_reflink, DUPEREMOVE


@requires_reflink
class AlreadySharedTest(DuperemoveTest):
    def test_independent_copies_still_dedupe(self):
        # Identical content in three independently-stored files (no reflink):
        # none share storage yet, so all must be deduped - a false "already
        # shared" skip here would silently lose dedupe.
        data = os.urandom(4 * 1024 * 1024)
        a = self.write("tree/a", data)
        b = self.write("tree/b", data)
        c = self.write("tree/c", data)
        self.sync()

        self.dedupe(self.path("tree"))
        self.assertDmOk()
        self.sync()
        self.assertShared(a, b, "independent copies a/b deduped")
        self.assertShared(a, c, "independent copies a/c deduped")

    def test_already_shared_is_skipped(self):
        data = os.urandom(4 * 1024 * 1024)
        base = self.write("tree/base", data)
        copy = self.reflink("tree/base", "tree/copy")   # already shares extents
        self.sync()
        before = open(base, "rb").read()

        # Run non-quiet so the summary's "Already shared" line is visible.
        self.out = subprocess.run(
            [DUPEREMOVE, "-rd", "--hashfile", self.hf, self.path("tree")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout

        self.assertDmOk()
        self.assertIn("Already shared", self.out, "skip is reported")
        self.sync()
        self.assertShared(base, copy, "still shared afterwards")
        self.assertEqual(before, open(base, "rb").read(), "data intact")

    def test_noop_rerun_after_dedupe(self):
        # After a first dedupe makes independent copies share, a second run
        # finds everything already shared and should change nothing.
        data = os.urandom(4 * 1024 * 1024)
        a = self.write("tree/a", data)
        b = self.write("tree/b", data)
        self.sync()
        self.dedupe(self.path("tree"))
        self.assertDmOk()
        self.sync()

        self.dedupe(self.path("tree"))
        self.assertDmOk()
        self.assertNoNewSharing()
        self.assertShared(a, b)
