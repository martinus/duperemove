# `--reuse-checksums` prototype (upstream #386)

Experimental, **opt-in** scan optimization: reuse an already-hashed file's
digests instead of re-reading and re-hashing data, when a file is byte-identical
to one already in the hashfile (same physical extents — snapshots, reflinks, or
anything a previous dedupe merged). Off by default; nothing changes unless you
pass `--reuse-checksums`.

## What it does

During the scan, for each file it fiemaps the extents and looks up
`extents(poff, len)` in the hashfile. If some already-scanned file has the exact
same size and the same physical extent at every logical offset, that file is
byte-identical, so its stored per-extent digests and whole-file digest are
copied in and **the data is never read**. A summary line reports how much was
skipped:

```
Checksum reuse: 8 files, 2.0 GiB not re-read
```

The produced hashfile is byte-for-byte identical to a normal scan (verified), so
dedupe behaves exactly the same afterward.

## How to A/B test on your data

```sh
# baseline (current behavior)
time duperemove -rd --hashfile=/tmp/a.hash /your/tree

# with reuse
time duperemove -rd --reuse-checksums --hashfile=/tmp/b.hash /your/tree
```

The win shows up wherever extents are **shared**: btrfs snapshots, reflink
copies, or a second tree (e.g. `git.bak`) that already shares extents with the
first. It scales with the sharing ratio — a tree of independent files gains
nothing (there's nothing to reuse), and unchanged files are already skipped by
the normal mtime check.

Two ways it hits:
- **Cross-run** (best): the hashfile persists, you scan again after a new
  snapshot appears — the snapshot's extents are already known, so it reads ~0.
- **Intra-run**: within one scan, the first copy of an extent is hashed and
  later copies reuse it. This is timing-dependent (a copy only reuses if its
  twin was already committed when it's reached), so a single fresh-hashfile run
  may reuse only some of the duplicates; a second run catches the rest.

Measured (snapshot rescan, 2 GiB reflinked copy, cold cache): **0.69s → 0.01s**.

## Prototype limitations (why it's not merge-ready)

- The reuse lookup uses per-call prepared statements under the scan write lock.
  A production version should cache the statements and read through a per-thread
  handle to avoid serializing the parallel scan.
- Only the default extent path is covered; `--dedupe-options=partial` (block
  hashes) falls back to reading.
- It builds and maintains an `extents(poff, len)` index while the option is on;
  that per-insert cost is part of what the A/B measures.
- Reusing a digest by physical offset across runs assumes the address still
  holds the same data. That's true for live btrfs extents, and the dedupe ioctl
  byte-verifies regardless, but a fully robust version might store/validate an
  extent generation.

Branch: `feature/reuse-checksums-386` — prototype for measurement, not for merge.
