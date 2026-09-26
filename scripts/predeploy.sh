#!/bin/sh
set -eu
candidate=${1:?usage: scripts/predeploy.sh EXACT_COMMIT_SHA}
test "$(git rev-parse HEAD)" = "$candidate" || { echo 'candidate SHA mismatch' >&2; exit 1; }
test -z "$(git status --porcelain)" || { echo 'working tree must be clean' >&2; exit 1; }
make test
printf 'Validated exact candidate %s\n' "$candidate"
