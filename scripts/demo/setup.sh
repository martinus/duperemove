#!/usr/bin/env bash
# Build a reproducible demo tree for the oans GIF.
#
# Most files are UNIQUE — they get hashed but never deduplicated — so the scan /
# hashing phase is the long, visible one. Only a small set of groups is
# duplicated (real copies, --reflink=never), so the dedupe phase has a little to
# do but stays short. Unique file sizes follow an exponential distribution (many
# small, a few large), seeded so the mix is reproducible.
#
#   usage: setup.sh <work-dir on btrfs or xfs>
set -euo pipefail

DEST="${1:?usage: setup.sh <work-dir on btrfs or xfs>}"
UNIQUE="${DEMO_UNIQUE:-2700}"         # unique files: hashed, never deduped (long scan)
DUP_GROUPS="${DEMO_DUP_GROUPS:-100}"  # duplicated groups: the (short) dedupe work
COPIES="${DEMO_COPIES:-3}"            # files per duplicated group (incl. the original)
MEAN_KB="${DEMO_MEAN_KB:-2048}"       # mean file size, KiB (exponential)
MIN_KB="${DEMO_MIN_KB:-16}"           # clamp: smallest file
MAX_KB="${DEMO_MAX_KB:-65536}"        # clamp: largest file (64 MiB)
SEED="${DEMO_SEED:-1}"                # RNG seed -> reproducible size mix

mkdir -p "$DEST"
fstype=$(stat -f -c %T "$DEST")
case "$fstype" in
  btrfs|xfs) ;;
  *) echo "error: $DEST is on '$fstype'; oans needs btrfs or xfs (reflink) or dedupe is a silent no-op." >&2
     exit 1 ;;
esac

rm -rf "$DEST/tree"; rm -f "$DEST"/demo.hash*
mkdir -p "$DEST/tree"

# Draw one size (KiB) per distinct content from an exponential distribution:
# s = -mean*ln(U), clamped to [MIN,MAX] and rounded to 4 KiB. Deterministic.
total_contents=$(( UNIQUE + DUP_GROUPS ))
mapfile -t sizes < <(awk -v n="$total_contents" -v mean="$MEAN_KB" -v min="$MIN_KB" \
                         -v max="$MAX_KB" -v seed="$SEED" 'BEGIN{
    srand(seed);
    for (i = 0; i < n; i++) {
      u = rand(); if (u < 1e-9) u = 1e-9;
      s = -mean * log(u);
      if (s < min) s = min; if (s > max) s = max;
      s = int(s / 4) * 4;   if (s < 4) s = 4;
      print s;
    }
  }')

# Write a file of N KiB of random data.
mkrand() { head -c "$(( $2 * 1024 ))" /dev/urandom > "$1"; }

echo "Generating $UNIQUE unique files + $DUP_GROUPS groups ×${COPIES} (exponential sizes, mean ${MEAN_KB} KiB) ..."

# Unique, non-duplicated files, spread across subdirs (300 per dir). Sizes
# [0 .. UNIQUE-1] are the uniques; [UNIQUE ..] are the group originals.
for i in $(seq 1 "$UNIQUE"); do
  d="$DEST/tree/data/set_$(printf '%03d' $(( (i - 1) / 300 )))"
  mkdir -p "$d"
  mkrand "$d/u_$(printf '%04d' "$i").bin" "${sizes[i - 1]}"
done

# Duplicated groups: one original + COPIES-1 real copies each.
for g in $(seq 1 "$DUP_GROUPS"); do
  d="$DEST/tree/dup/group_$(printf '%03d' "$g")"
  mkdir -p "$d"
  mkrand "$d/original.bin" "${sizes[UNIQUE + g - 1]}"
  for c in $(seq 1 "$(( COPIES - 1 ))"); do
    cp --reflink=never "$d/original.bin" "$d/copy_$(printf '%02d' "$c").bin"
  done
done

# Reclaimable = sum over groups of (COPIES-1) x group size.
reclaim_kb=0
for g in $(seq 1 "$DUP_GROUPS"); do
  reclaim_kb=$(( reclaim_kb + sizes[UNIQUE + g - 1] * (COPIES - 1) ))
done
printf 'tree: %s  (%d files = %d unique + %d groups x%d; ~%d MiB reclaimable across %d groups)\n' \
  "$(du -sh "$DEST/tree" | cut -f1)" \
  "$(( UNIQUE + DUP_GROUPS * COPIES ))" \
  "$UNIQUE" "$DUP_GROUPS" "$COPIES" \
  "$(( reclaim_kb / 1024 ))" "$DUP_GROUPS"
