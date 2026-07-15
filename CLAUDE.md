# duperemove — working notes for Claude

`duperemove` finds duplicate extents and deduplicates them via the kernel
`FIDEDUPERANGE` ioctl (atomic, byte-verified). Hashes live in a SQLite
**hashfile** (WAL mode, `synchronous=OFF`, `cache_size=-256000`).

## Build & test

```sh
make -j$(nproc)                         # builds duperemove + helpers
make check                              # C unit tests (test.c) + Python integration suite
DUPEREMOVE=./duperemove python3 tests/run.py     # integration suite only
```

Integration tests are Python stdlib `unittest` (no extra deps); they drive the
built binary against a scratch tree and assert on the hashfile and on-disk
sharing. Dedupe cases need a reflink-capable fs — override with
`DUPEREMOVE_TEST_DIR=/mnt/btrfs`. Keep tests in `tests/`; don't add shell tests.

### Building on Fedora

Missing headers (`uuid/uuid.h`, libbsd `queue.h`, xxhash) come from a dev shim:
put `.pc` files under `/tmp/devroot/pc` and build with
`PKG_CONFIG_PATH=/tmp/devroot/pc make`. This is a local workaround, not part of
the repo — don't commit it.

## Profiling & measurement — read this before optimizing

Startup/scan cost has burned us before. The rules:

- **Never draw conclusions from `strace -c`.** Its per-syscall interception
  overhead inflates whatever is called most often. It once reported `statx` at
  66% (it's really ~7%) and completely hid the actual hotspot, which was
  per-file SQLite WAL locking. Use **`perf record -g --call-graph dwarf`** +
  `perf report` for where time goes, and **`perf stat -e task-clock`** for A/B
  wall-clock.
- **When A/B-testing two builds, build two distinctly-named binaries** (e.g.
  `/tmp/dm-base`, `/tmp/dm-batch`) and confirm they actually differ before
  trusting the numbers. A `git stash` + `make` that silently reused a stale
  object file once made a binary look identical to itself → a real ~24% win got
  wrongly dismissed as "no effect." Interleave runs to cancel drift.
- **A single surprising result that contradicts prior profiling is probably a
  measurement bug**, not a discovery. Reconcile before acting.

## Hashfile / SQLite gotchas

- In WAL mode a connection holds its read snapshot across queries. Wrapping the
  per-file change-detection reads in **one batched read transaction** (refreshed
  ~10s), instead of an implicit transaction per file, cut `F_SETLK` from ~2/file
  (283k on a 141k-file rescan) to ~800 total, ~24% faster. The writer batches on
  the same ~10s cadence so the reader snapshot doesn't pin the WAL against
  checkpointing. Reader and writer must stay **separate SQLite connections**.
- The listing thread reads through the listing handle (`db`) and writes through
  the batched writer handle (`wdb`/`scan_writer`) — keep that split.
- `.hashfile-wal` and `.hashfile-shm` are SQLite WAL sidecars. Normal, don't
  hand-delete them.
- **Hardlink hazard:** `INSERT OR REPLACE` on `UNIQUE(ino, subvol)` can cascade-
  delete rows for other links to the same inode. An in-memory `seen_inodes` set
  guards this; a batch that aborts here can silently empty the hashfile while
  exiting 0. There's a regression test — keep it.

## dedupe_seq (incremental dedup)

Scan assigns `seq = config+1`, bumped every `--batchsize`/`-B` files (default
1024). `process_duplicates` loops `for i=dedupe_seq; i<max` over generations;
each group is deduped exactly once regardless of batch size (verified — a
no-change rerun nets 0). Don't "fix" cross-generation reprocessing; it isn't
happening.

## Correctness invariants

- Ctrl+C is safe: `FIDEDUPERANGE` is atomic and the hashfile stays WAL-consistent
  on process kill. Only power loss risks the hashfile (due to `synchronous=OFF`).
- A no-op rescan must net **0** changes and leave row counts identical. Use this
  as a smoke test after any scan-path change.
