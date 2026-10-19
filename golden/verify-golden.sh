#!/usr/bin/env bash
# Compare a stage 3 run against the golden outputs, byte for byte.
# usage: golden/verify-golden.sh <24|8> <data dir of the run>
#   24 = tier-c/smoke inputs (screening tier), 8 = tier-c/smoke-script inputs (fast tier)
# Exit 0 only if the same files exist with identical contents, and nothing extra or missing.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tier=${1:?usage: verify-golden.sh <24|8> <data dir>}
run=${2:?usage: verify-golden.sh <24|8> <data dir>}
gold="$here/golden-$tier"
[ -d "$gold" ] || { echo "no $gold" >&2; exit 2; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp" "$tmp.diff"' EXIT
"$here/collect.sh" "$run" "$tmp"
if diff -rq "$gold" "$tmp" > "$tmp.diff"; then
	echo "PASS: $(find "$gold" -type f | wc -l) files identical to golden-$tier"
else
	head -40 "$tmp.diff"; echo "FAIL: $(wc -l < "$tmp.diff") differences from golden-$tier (first 40 shown)" >&2; rm -f "$tmp.diff"; exit 1
fi
