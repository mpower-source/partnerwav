#!/bin/bash
# Runs supabase/*.sql against a throwaway local Postgres 16 with a Supabase stand-in (tests/sql/supabase_shim.sql).
set -e
D=/var/tmp/partnerwav-pg; PORT=55432; BIN=/usr/lib/postgresql/16/bin; ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -x $BIN/initdb ]; then echo "SKIP: PostgreSQL 16 not installed"; exit 0; fi
su postgres -c "$BIN/pg_ctl -D $D/data stop -m fast" >/dev/null 2>&1 || true
rm -rf $D; mkdir -p $D; chown postgres $D
su postgres -c "$BIN/initdb -D $D/data -A trust -U postgres" >/dev/null
su postgres -c "$BIN/pg_ctl -D $D/data -o '-p $PORT -k $D' -l $D/log start" >/dev/null; sleep 1.5
P="psql -h $D -p $PORT -U postgres -q -v ON_ERROR_STOP=1"
$P -f "$ROOT/tests/sql/supabase_shim.sql"
# portal_users.sql minus its STEP 2 role-assignment block
sed '/^with wanted/,$d' "$ROOT/supabase/portal_users.sql" | $P
$P -f "$ROOT/supabase/portal_records.sql"
$P -f "$ROOT/supabase/portal_records.sql"   # re-runnable
psql -h $D -p $PORT -U postgres -q -f "$ROOT/tests/sql/test_portal_records.sql" 2>/dev/null | sed 's/^ //' | grep -E '^(PASS|FAIL)' | tee /tmp/sqlres.txt
su postgres -c "$BIN/pg_ctl -D $D/data stop -m fast" >/dev/null
P_=$(grep -c ^PASS /tmp/sqlres.txt); F_=$(grep -c ^FAIL /tmp/sqlres.txt || true)
echo "test_sql: $P_ passed, $F_ failed"; [ "$F_" = "0" ]
