"""--skip-zeroes must test the block actually being hashed, not always the
first block of the buffer.

Regression test for the bug fixed upstream in markfasheh/duperemove#405, where
is_block_zeroed() was run on `buffer->buf + buffer->dl_offset` (always block 0)
instead of block #i. That made --skip-zeroes either skip every block or skip
none, depending only on whether the first block happened to be zero.
"""

import os
from harness import DuperemoveTest

BS = 4096


class SkipZeroesTest(DuperemoveTest):
    def _hashed_offsets(self, *blocks):
        """Scan a single file made of the given 4K blocks with block hashing +
        --skip-zeroes, and return the loffs of the blocks that got hashed."""
        self.write("f", b"".join(blocks))
        self.scan(self.path("f"), "-b", str(BS),
                  "--dedupe-options=partial", "--skip-zeroes")
        self.assertDmOk()
        return sorted(r[0] for r in self.hf_query("select loff from blocks"))

    def test_trailing_zero_block_is_skipped(self):
        # [random][zeros]: only block 0 should be hashed.
        # The bug tested block 0 (random) for both -> hashed [0, BS].
        self.assertEqual([0], self._hashed_offsets(os.urandom(BS), b"\0" * BS))

    def test_leading_zero_block_does_not_skip_the_rest(self):
        # [zeros][random]: block 1 must still be hashed.
        # The bug tested block 0 (zeros) for both -> hashed nothing.
        self.assertEqual([BS], self._hashed_offsets(b"\0" * BS, os.urandom(BS)))
