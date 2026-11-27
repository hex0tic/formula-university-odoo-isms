#!/usr/bin/env bash
# Run inside a CI runner with Docker; never use a shared/production database.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mode="${1:?expected install or upgrade}"
baseline="${2:-}"
test "$mode" = install || test "$mode" = upgrade
if [[ "$mode" == upgrade ]]; then
  test -f "$baseline/university_isms/__manifest__.py"
  baseline="$(realpath "$baseline")"
fi

id="formula-ci-${RANDOM}-$$"
password="$(openssl rand -hex 24)"
tmp="$(mktemp -d)"
cleanup() {
  docker rm -fv "$id-db" >/dev/null 2>&1 || true
  docker volume rm "$id-data" >/dev/null 2>&1 || true
  docker network rm "$id" >/dev/null 2>&1 || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT
docker network create --internal "$id" >/dev/null
docker volume create "$id-data" >/dev/null
docker run -d --name "$id-db" --network "$id" --network-alias db \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD="$password" \
  "${FORMULA_CI_POSTGRES_IMAGE:-postgres:16-alpine}" -c jit=off >/dev/null
for _ in {1..60}; do
  # Wait for the listener that Odoo uses, not the bootstrap Unix socket.
  docker exec "$id-db" pg_isready -h 127.0.0.1 -U odoo -d postgres >/dev/null 2>&1 && break
  [[ "$(docker inspect -f '{{.State.Running}}' "$id-db")" == true ]] || break
  sleep 1
done
if ! docker exec "$id-db" pg_isready -h 127.0.0.1 -U odoo -d postgres; then
  docker logs "$id-db"
  exit 1
fi

run_odoo() {
  local path="$1"
  shift
  docker run --rm --network "$id" \
    -e HOST=db -e USER=odoo -e PASSWORD="$password" \
    -v "$path:/mnt/extra-addons:ro" -v "$id-data:/var/lib/odoo" \
    "${FORMULA_CI_ODOO_IMAGE:-odoo:18.0}" odoo -d formula_ci \
    --db-filter='^formula_ci$' --without-demo=all --stop-after-init \
    --http-interface=127.0.0.1 --max-cron-threads=0 --workers=0 "$@"
}
list_modules() {
  find "$1" -mindepth 2 -maxdepth 2 -name __manifest__.py -printf '%h\n' |
    sed 's#.*/##' | LC_ALL=C sort
}
csv() { paste -sd,; }
list_modules "$root/odoo/addons" > "$tmp/current"
tags="$(sed 's#^#/#' "$tmp/current" | csv)"
if [[ "$mode" == install ]]; then
  run_odoo "$root/odoo/addons" -i "$(csv < "$tmp/current")" --test-tags "$tags" |& tee "$tmp/odoo.log"
else
  list_modules "$baseline" > "$tmp/base"
  comm -12 "$tmp/base" "$tmp/current" > "$tmp/existing"
  comm -13 "$tmp/base" "$tmp/current" > "$tmp/new"
  run_odoo "$baseline" -i "$(csv < "$tmp/base")"
  docker exec "$id-db" psql -U odoo -d formula_ci -XAt -c \
    "SELECT name FROM ir_module_module WHERE state = 'installed'" | LC_ALL=C sort > "$tmp/installed"
  comm -23 "$tmp/base" "$tmp/installed" > "$tmp/missing"
  if [[ -s "$tmp/missing" ]]; then
    cat "$tmp/missing" >&2
    echo 'PR baseline modules failed to install' >&2
    exit 1
  fi
  opts=(-u "$(csv < "$tmp/existing")")
  if [[ -s "$tmp/new" ]]; then opts+=(-i "$(csv < "$tmp/new")"); fi
  run_odoo "$root/odoo/addons" "${opts[@]}" --test-tags "$tags" |& tee "$tmp/odoo.log"
fi
grep -Eq '0 failed, 0 error\(s\) of [1-9][0-9]* tests' "$tmp/odoo.log"
