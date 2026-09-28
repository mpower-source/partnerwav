#!/usr/bin/env bash
# Browser tests for partnerwav-v11-merged.html (needs: pip install playwright && playwright install chromium)
# Each test starts from a clean browser profile, so localStorage from earlier runs doesn't leak in.
cd "$(dirname "$0")"
fail=0
for t in test_*.py; do
  out=$(python3 "$t" 2>&1)
  p=$(echo "$out" | grep -c '^PASS'); f=$(echo "$out" | grep -c '^FAIL')
  echo "$t: $p passed, $f failed"
  echo "$out" | grep -E '^FAIL|Traceback|JS ERRORS: \[.+\]'
  [ "$f" -gt 0 ] && fail=1
  echo "$out" | grep -q 'JS ERRORS: \[\]' || fail=1
done
# Supabase SQL (row-level security + guard trigger) against a local PostgreSQL, if installed
out=$(./test_sql.sh 2>&1 | tail -1); echo "$out"; echo "$out" | grep -q ' 0 failed' || echo "$out" | grep -q SKIP || fail=1
exit $fail
