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

## When it actually helps (measured)

The reuse skips *reading and hashing*, so it only speeds up the wall clock when
reading is the bottleneck:

- **Large files / slow disk / huge shared sets** (the 36.5 TB-of-snapshots case
  in the issue): big win. Measured cross-run, 8×256 MB reflinked snapshot, cold
  cache: **9.0s → 2.0s**.
- **Many small files on fast storage** (e.g. git repos on NVMe): the scan is
  *metadata-bound*, not read-bound, so even though the reads are skipped the
  wall time barely moves. Measured 4000×1 MB reflinked twins, cold cache:
  2.03s → 2.03s (2 GiB not re-read, but no wall-time gain). Don't expect this
  workflow to benefit.

Hit-rate note: the lookup reads through a per-thread connection that sees the
scan writer's *committed* batches. So the strong case is **cross-run** (a
snapshot appears, you rescan with the hashfile from before) where the originals
are already committed. **Intra-run** reuse (a tree and its twin scanned in one
fresh-hashfile run) only hits for copies whose twin was already committed when
they're reached, which is timing-dependent and can be low.

## Prototype limitations (why it's not merge-ready)

- Each scan worker opens its own read handle (`dbfile_open_reader`) and caches
  the lookup statements thread-locally; those handles are never explicitly
  closed (the OS reclaims them at exit). A production version would own their
  lifecycle.
- The reader sees only *committed* batches, which caps intra-run hit rate (see
  the hit-rate note above). A production version might commit more eagerly or
  keep a small in-memory index of extents hashed this run.
- Only the default extent path is covered; `--dedupe-options=partial` (block
  hashes) falls back to reading.
- It builds and maintains an `extents(poff, len)` index while the option is on;
  that per-insert cost is part of what the A/B measures, and on a
  low-sharing/metadata-bound tree it can make the scan slightly slower.
- Reusing a digest by physical offset across runs assumes the address still
  holds the same data. That's true for live btrfs extents, and the dedupe ioctl
  byte-verifies regardless, but a fully robust version might store/validate an
  extent generation.

Branch: `feature/reuse-checksums-386` — prototype for measurement, not for merge.
