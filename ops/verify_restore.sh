#!/usr/bin/env bash
# Compare a source database against a restored one and print PASS/FAIL. The
# checksum over id ordered by id catches missing, extra, or altered rows that a
# bare row count would miss. Exits non-zero on FAIL so a caller can gate on it.
set -euo pipefail

SOURCE_DB="${1:-${PGDATABASE:-dropme}}"
RESTORED_DB="${2:-${SCRATCH_DB:-dropme_restore_test}}"

fingerprint() {
  psql -d "$1" -tA -F '|' -v ON_ERROR_STOP=1 -c \
    "SELECT count(*),
            coalesce(min(created_at)::text, ''),
            coalesce(max(created_at)::text, ''),
            coalesce(md5(string_agg(id::text, ',' ORDER BY id)), '')
     FROM events;"
}

echo "[verify] source='$SOURCE_DB'  restored='$RESTORED_DB'"
src="$(fingerprint "$SOURCE_DB")"
dst="$(fingerprint "$RESTORED_DB")"

IFS='|' read -r s_count s_min s_max s_md5 <<<"$src"
IFS='|' read -r d_count d_min d_max d_md5 <<<"$dst"

printf '%-12s %-24s %-24s\n' "field" "source" "restored"
printf '%-12s %-24s %-24s\n' "count" "$s_count" "$d_count"
printf '%-12s %-24s %-24s\n' "min(created)" "$s_min" "$d_min"
printf '%-12s %-24s %-24s\n' "max(created)" "$s_max" "$d_max"
printf '%-12s %-24s %-24s\n' "md5(ids)" "${s_md5:0:16}…" "${d_md5:0:16}…"

if [[ "$src" == "$dst" ]]; then
  echo "[verify] PASS"
else
  echo "[verify] FAIL"
  exit 1
fi
