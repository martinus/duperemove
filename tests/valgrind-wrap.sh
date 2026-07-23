#!/bin/sh
#
# valgrind-wrap.sh - run oans under valgrind's memcheck, transparently.
#
# The integration harness execs a single binary named by $DUPEREMOVE, so point
# that at this script to put every oans invocation under valgrind:
#
#   OANS_VG_LOGDIR=/tmp/vglogs \
#   DUPEREMOVE=tests/valgrind-wrap.sh python3 tests/run.py
#
# (or just `make integration-valgrind`, which wires this up and checks the logs).
#
# Env knobs:
#   OANS_BIN        the real binary to run (default: ./oans next to this script)
#   OANS_VG_LOGDIR  if set, valgrind writes one log per pid here (vg.<pid>.log)
#                   instead of stderr - keeps its output out of the harness's
#                   captured stdout, so a non-empty log == a real finding.
#
# A definite/possible leak or any memory error also flips the exit code to 42.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${OANS_BIN:=$here/../oans}"

logopt=
[ -n "${OANS_VG_LOGDIR:-}" ] && logopt="--log-file=$OANS_VG_LOGDIR/vg.%p.log"

exec valgrind -q \
	--leak-check=full \
	--errors-for-leak-kinds=definite,possible \
	--error-exitcode=42 \
	--suppressions="$here/valgrind.supp" \
	$logopt \
	"$OANS_BIN" "$@"
