#!/usr/bin/env bash
#
# verify.sh - one-shot pre-PR gate. Runs, and stops at the first failure:
#
#   1. build (make -j) - any compiler warning is treated as a failure
#   2. C unit tests           (make test)
#   3. Python integration suite
#   4. a valgrind scan + dedupe + bare-replay smoke
#
# Exits non-zero on the first failure, zero when everything passes.
#
# Honors the usual environment knobs (nothing repo-specific is baked in):
#   PKG_CONFIG_PATH      extra pkg-config search path (e.g. a local dev shim)
#   DUPEREMOVE_TEST_DIR  scratch dir for the integration suite and the valgrind
#                        smoke; dedupe needs a reflink fs (btrfs/xfs). Defaults
#                        to the harness default (.itest-scratch next to the repo).
#
set -euo pipefail

cd "$(dirname "$0")/.."
step() { printf '\n=== %s ===\n' "$1"; }

step "build (make -j, warnings are failures)"
out=$(make -j"$(nproc)" 2>&1) || { echo "$out"; exit 1; }
echo "$out"
if echo "$out" | grep -iEq 'warning:|error:'; then
	echo "verify: build produced warnings/errors" >&2
	exit 1
fi

step "unit + integration tests (make check)"
make check

step "valgrind smoke (scan + dedupe + bare replay)"
if ! command -v valgrind >/dev/null 2>&1; then
	echo "valgrind not installed - skipping smoke"
else
	scratch=$(mktemp -d "${DUPEREMOVE_TEST_DIR:-${TMPDIR:-/tmp}}/verify-smoke.XXXXXX")
	trap 'rm -rf "$scratch"' EXIT
	head -c 1048576 /dev/urandom > "$scratch/a"
	cp "$scratch/a" "$scratch/b"		# a real duplicate for dedupe to act on
	hf="$scratch/hf.db"
	vg() {
		valgrind -q --leak-check=full --error-exitcode=42 \
			--suppressions=tests/valgrind.supp "$@"
	}
	vg ./oans -rd --hashfile="$hf" "$scratch" >/dev/null
	vg ./oans --hashfile="$hf" >/dev/null	# bare replay of the stored config
	echo "ok"
fi

printf '\nALL CHECKS PASSED\n'
