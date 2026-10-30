#!/usr/bin/env bash
# Respaldo privado; --verify restaura en un contenedor sin red ni volumen original.
set -euo pipefail
umask 077
stamp=$(date -u +%Y%m%dT%H%M%S%N)
destination="backups/$stamp"
mkdir -p "$destination"
chmod 700 "$destination"
docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$destination/database.dump"
docker compose exec -T db sh -c 'exec pg_dumpall -U "$POSTGRES_USER" --globals-only' > "$destination/globals.sql"
docker compose exec -T db pg_restore --list < "$destination/database.dump" > "$destination/restore-list.txt"
(cd "$destination" && sha256sum database.dump globals.sql > SHA256SUMS && sha256sum -c SHA256SUMS)
sha256sum .env > "$destination/env.sha256"
if [[ ${1:-} == --verify ]]; then
  container="medinet-restore-$stamp"
  image=$(docker inspect --format '{{.Config.Image}}' "$(docker compose ps -q db)")
  docker run -d --name "$container" --network none --mount type=tmpfs,destination=/var/lib/postgresql/data \
    -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=restore_test "$image" > /dev/null
  trap 'docker stop "$container" > /dev/null' EXIT
  ready=false
  for _ in {1..60}; do
    if docker exec "$container" pg_isready -h 127.0.0.1 -U postgres > /dev/null 2>&1; then ready=true; break; fi
    sleep 1
  done
  "$ready"
  docker exec -i "$container" pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d restore_test < "$destination/database.dump"
  for table in operating_rooms patients medical_staff surgeries surgery_staff app_users alembic_version; do
    # Nombres fijos del código; ningún identificador proviene del usuario.
    query="SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text), '')) FROM $table t"
    docker compose exec -T db sh -c 'exec psql -XAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh "$query" > "$destination/$table.original"
    docker exec "$container" psql -XAt -v ON_ERROR_STOP=1 -U postgres -d restore_test -c "$query" > "$destination/$table.restored"
    cmp "$destination/$table.original" "$destination/$table.restored"
  done
  printf 'Restauración completa; siete tablas coinciden.\n' > "$destination/verification.txt"
fi
printf 'Respaldo privado comprobado: %s\n' "$destination"
