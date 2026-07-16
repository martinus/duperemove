# Upstream open issues vs. this fork

All **59 open** issues on
[markfasheh/duperemove](https://github.com/markfasheh/duperemove/issues) as of
2026-07-16, assessed against this fork (`martinus/duperemove`, current
`master`). Most verdicts come from reading the fork's code / from this
session's changes; only a few were reproduced locally, and those are called
out. Nothing here was confirmed by reproducing the upstream bug except where
noted.

Legend: ✅ fixed/addressed in fork · ⚠️ still affected · ❌ out of scope / not a
code bug · ❓ unverified (needs a repro).

## Addressed by this fork

| # | Title | Basis |
|---|-------|-------|
| [#398](https://github.com/markfasheh/duperemove/issues/398) | ioctl returns 22 (EINVAL) | ✅ Request length clamped to real file size (`clamp_len_to_ioctl_file`) + skip destinations changed since scan. Tests `test_einval.py` (cites #398), `test_changed_since_scan.py`. |
| [#292](https://github.com/markfasheh/duperemove/issues/292) | Process largest chunks first | ✅ `push_extents()` now sorts by verify work and pushes largest-first (LPT). Exactly this request. |
| [#379](https://github.com/markfasheh/duperemove/issues/379) | "Database is locked" | ✅ `PRAGMA busy_timeout = 30000` added (`dbfile.c:314`), so transient lock contention retries instead of erroring. |
| [#350](https://github.com/markfasheh/duperemove/issues/350) | No final summary (one per batch) | ✅ `dedupe_end()` prints a single aggregated summary across all batches; per-batch net-change line only in piped/`-q` mode. |
| [#159](https://github.com/markfasheh/duperemove/issues/159) | Please add a time-to-finish estimate | ✅ ETA added to both scan and dedupe status. (The 405-day pathological case is the separate slow-dedupe/hang class below.) |
| [#378](https://github.com/markfasheh/duperemove/issues/378) | Exclude files by size | ✅ `--min-filesize` added. |
| [#395](https://github.com/markfasheh/duperemove/issues/395) | Incorrect `-nan%` (0/0) | ✅ `percent()` guards `val2==0`; scan totals print `… : 100.0`. |
| [#391](https://github.com/markfasheh/duperemove/issues/391) | Crash on path > PATH_MAX | ✅ Walk now `continue`s past over-long paths (`file_scan.c:869`) instead of `abort()`. |
| [#358](https://github.com/markfasheh/duperemove/issues/358) | `--std=c23` unrecognized on gcc12 | ✅ Fork builds with `-std=gnu11`. |
| [#383](https://github.com/markfasheh/duperemove/issues/383) | `-q` doesn't suppress the "format under development" warning | ✅ That warning no longer exists in the fork's output. |
| [#286](https://github.com/markfasheh/duperemove/issues/286) | Progress indicator not predictable | ✅ (mostly) Dedupe bar never claims a false 100% (capped 99% while working); scan shows both files and bytes. The "100% then a whole other phase" surprise for the dedupe bar is gone. |
| [#168](https://github.com/markfasheh/duperemove/issues/168) | Dedupe increases fragmentation | ✅ (partial) Least-fragmented-target selection stops copies inheriting a fragmented target's layout. Doesn't defrag existing fragmentation (see #213). |
| [#397](https://github.com/markfasheh/duperemove/issues/397) | `--hashfile` dislikes leading-`-` paths | ✅ Not reproducible on the fork (ran `--hashfile=-srv-dak-.hashes`, deduped cleanly). |

## Still affected — bugs worth fixing

| # | Title | Basis |
|---|-------|-------|
| [#396](https://github.com/markfasheh/duperemove/issues/396) / [#407](https://github.com/markfasheh/duperemove/issues/407) | Infinite loop / hang during dedupe | ⚠️ No zero-progress guard in `dedupe_extents()`: a round that dedupes 0 bytes with `status==0` while `len ≥ blocksize` requeues forever. The 32 MB round cap helps responsiveness but doesn't stop the spin. Likely the same root cause as several hang reports below. **Highest-value fix.** |
| [#370](https://github.com/markfasheh/duperemove/issues/370) / [#305](https://github.com/markfasheh/duperemove/issues/305) / [#319](https://github.com/markfasheh/duperemove/issues/319) | Hang with partial + hashfile / slow IO | ⚠️ Same hang class as #396/#407 (unverified individually). |
| [#331](https://github.com/markfasheh/duperemove/issues/331) | Re-dedupes already-shared extents (snapshots) | ⚠️ Fork improves throughput (LPT, batching) but still issues ioctls on already-shared extents; the "80 identical ISOs re-deduped" waste largely persists. |
| [#374](https://github.com/markfasheh/duperemove/issues/374) | Extent handling broken on compressed FS | ⚠️ The fiemap `fe_logical/fe_length` vs in-memory-offset mismatch is unchanged; "file changed" / "unable to get extent" on compressed btrfs likely persists. |
| [#389](https://github.com/markfasheh/duperemove/issues/389) | Crash: `--fdupes` with hard links | ⚠️ `abort_lineno()` at `filerec.c:140` still fires on a duplicate fileid; the hardlink guard added this session is in the scan path, not the `--fdupes` path. |
| [#353](https://github.com/markfasheh/duperemove/issues/353) | Control chars in filenames block the terminal | ⚠️ Status/table output prints filenames verbatim; no sanitizing of control bytes. |
| [#394](https://github.com/markfasheh/duperemove/issues/394) | 32-bit progress shows total 0 (`3/0`) | ⚠️ Fork still prints 64-bit counters with `%lu`; UB on i386/armel. Needs `PRIu64`. 64-bit unaffected. |
| [#382](https://github.com/markfasheh/duperemove/issues/382) | `-d <path>` dedupes whole hashfile, not the path | ⚠️ Unchanged design: the dedupe phase works from hashfile generations, ignoring the path argument. |
| [#251](https://github.com/markfasheh/duperemove/issues/251) | No pre-check for NoCOW (+C) attribute | ⚠️ Not checked up front; ties into the hang class (#396). |
| [#348](https://github.com/markfasheh/duperemove/issues/348) | Search status `pos == NaN` | ⚠️ (minor) `psearch` still computes `processed/total` unguarded; NaN if total is 0. Reworked code path, low impact. |
| [#155](https://github.com/markfasheh/duperemove/issues/155) / [#176](https://github.com/markfasheh/duperemove/issues/176) | Confusing per-file statuses (-18, status 0) | ⚠️ Kernel-returned statuses; fork now aggregates errors in the summary but doesn't explain each. |
| [#351](https://github.com/markfasheh/duperemove/issues/351) | Keeps trying to dedupe a file that no longer exists | ✅ (partial) On `ENOENT` the fork removes the file from the hashfile during dedupe; the changed-since-scan skip covers files that shrank/grew. A stale hashfile no longer errors per-attempt. |

## Performance / architecture (partly improved, not solved)

| # | Title | Basis |
|---|-------|-------|
| [#401](https://github.com/markfasheh/duperemove/issues/401) / [#371](https://github.com/markfasheh/duperemove/issues/371) / [#393](https://github.com/markfasheh/duperemove/issues/393) / [#306](https://github.com/markfasheh/duperemove/issues/306) | io-threads slow on HDD / partial | ⚠️ Fork caps auto threads at 8 but has no rotational detection or sequential mode; concurrent I/O on HDD still thrashes. #393's patch targets upstream's (now-changed) walk. |
| [#381](https://github.com/markfasheh/duperemove/issues/381) | Hashfile dedupe much slower after upgrade | ❓ Fork did substantial hashfile/index/perf work; not measured against this report. |
| [#88](https://github.com/markfasheh/duperemove/issues/88) / [#386](https://github.com/markfasheh/duperemove/issues/386) | Re-reads/re-hashes unchanged extents across snapshots | ⚠️ No per-extent checksum reuse; unchanged snapshot data is re-hashed. Incremental scan skips unchanged *files*, not shared extents across subvolumes. |

## Filesystem / environment support

| # | Title | Basis |
|---|-------|-------|
| [#380](https://github.com/markfasheh/duperemove/issues/380) / [#312](https://github.com/markfasheh/duperemove/issues/312) | ZFS: `csum_by_extent` ENOTSUP; want non-fiemap dedupe | ⚠️ Fork still requires fiemap for checksumming; ZFS only works via `--fdupes`. |
| [#342](https://github.com/markfasheh/duperemove/issues/342) | Support bcachefs | ❌ Feature/support request; reflink FSes beyond btrfs/xfs untested. |
| [#363](https://github.com/markfasheh/duperemove/issues/363) | `-d` "succeeds" on NFS | ❓ Feature-probe/test harness concern; not reproduced. |
| [#250](https://github.com/markfasheh/duperemove/issues/250) | Corruption via active gocryptfs (fuse) mount | ❓ Deduping a fuse view is unsupported; not investigated. |
| [#199](https://github.com/markfasheh/duperemove/issues/199) | EINVAL as non-root (old 4.4 kernel) | ❓ Kernel-era specific; likely N/A on modern kernels. |
| [#314](https://github.com/markfasheh/duperemove/issues/314) / [#189](https://github.com/markfasheh/duperemove/issues/189) / [#191](https://github.com/markfasheh/duperemove/issues/191) | RO-subvolume / snapshot dedupe semantics | ❌ Questions about read-only subvolumes & unsharing; behavior unchanged. |

## Feature requests (out of scope / unimplemented in fork)

| # | Title | Note |
|---|-------|------|
| [#404](https://github.com/markfasheh/duperemove/issues/404) | Handle in-use executables (ETXTBSY) | ⚠️ Still just skipped; no busy-file list / reflink-swap. |
| [#400](https://github.com/markfasheh/duperemove/issues/400) | rsync from the hashfile | ❌ External-tool idea. |
| [#213](https://github.com/markfasheh/duperemove/issues/213) | Defrag while dedup | ❌ Not implemented (would complement #168). |
| [#204](https://github.com/markfasheh/duperemove/issues/204) | Duplication-ratio-only report | ❌ Not added. |
| [#215](https://github.com/markfasheh/duperemove/issues/215) | systemd units | ❌ Packaging. |
| [#185](https://github.com/markfasheh/duperemove/issues/185) | Rolling-window hash | ❌ Analyzed earlier this project: not useful (reflink needs 4K alignment). |
| [#27](https://github.com/markfasheh/duperemove/issues/27) | overlayfs-like listing/revert | ❌ Out of scope. |

## Packaging / build / release / docs

| # | Title | Note |
|---|-------|------|
| [#367](https://github.com/markfasheh/duperemove/issues/367) | 0.15 fails to build (struct redefinition) | ✅ Fork builds clean under CI. |
| [#387](https://github.com/markfasheh/duperemove/issues/387) | Tarball Makefile runs `git describe` | ⚠️ Release-tarball tooling; fork Makefile still derives version from git. |
| [#388](https://github.com/markfasheh/duperemove/issues/388) | `show-shared-extents` script not installed | ⚠️ Minor install-target gap; not checked in fork. |
| [#313](https://github.com/markfasheh/duperemove/issues/313) | No 0.13 RPM for AlmaLinux 9 | ❌ Distro packaging. |

## Old / unreproducible / needs info

| # | Title | Note |
|---|-------|------|
| [#392](https://github.com/markfasheh/duperemove/issues/392) | Abort after long XFS dedupe | ❓ Same asserts still present in `dedupe_extent_list`; cause unknown, not reproduced. |
| [#372](https://github.com/markfasheh/duperemove/issues/372) | Crash `hash-tree.c:68` (v0.11.2) | ❓ Very old; after I/O read errors. Not reproduced. |
| [#337](https://github.com/markfasheh/duperemove/issues/337) | Early SIGSEGV in DB init (non-deterministic) | ❓ No backtrace; not reproduced. |

## Recommended next fixes (highest value)

1. **Zero-progress guard in `dedupe_extents()`** — closes the hang cluster
   #396/#407 (and likely #370/#305/#319, and the pathological #159). Stop a
   request when a round dedupes 0 bytes with `status==0` and `len` doesn't
   move.
2. **`%lu` → `PRIu64` in `progress.c`** — fixes 32-bit output (#394); tiny.
3. **`--fdupes` hardlink guard** — dedupe by `(ino, subvol)` before inserting a
   filerec to avoid the `filerec.c:140` abort (#389).
4. **Send the #398 EINVAL fix upstream** — not present there; resolves #398.
5. **Skip already-shared extents** before issuing the ioctl (#331) — real win on
   snapshot-heavy trees.
