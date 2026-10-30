#!/usr/bin/env bash
# Solo actualiza API/web de una instalación preparada. Nunca cambia .env ni DB.
set -euo pipefail
set +x
umask 077
sha=${1:?Uso: deploy.sh SHA [directorio]}
[[ $sha =~ ^[0-9a-f]{40}$ ]] || { echo 'SHA inválido' >&2; exit 2; }
root=$(realpath "${2:-/opt/medinet-pab}")
state="$root/.deployment"
mkdir -p "$state"
chmod 700 "$state"
exec 9>"$state/deploy.lock"
flock -n 9 || { echo 'Otro despliegue está activo' >&2; exit 1; }
for file in "$root/.env" "$root/.env.runtime" "$state/current.env"; do
  [[ -f $file ]] || { echo 'Falta configuración privada o release inicial verificado' >&2; exit 1; }
  [[ $(stat -c '%a' "$file") == 600 ]] || { echo 'Configuración debe tener permisos 0600' >&2; exit 1; }
done
prefix=''
previous_tag=''
db_tag=''
while IFS='=' read -r key value; do
  case "$key" in
    IMAGE_PREFIX) prefix=$value ;;
    IMAGE_TAG) previous_tag=$value ;;
    POSTGRES_IMAGE_TAG) db_tag=$value ;;
    ''|'#'*) ;;
    *) echo 'Estado de release no admitido' >&2; exit 1 ;;
  esac
done < "$state/current.env"
[[ $prefix =~ ^ghcr\.io/[a-z0-9._-]+/[a-z0-9._-]+$ ]] || { echo 'Prefijo GHCR inválido' >&2; exit 1; }
[[ $previous_tag =~ ^sha-[0-9a-f]{40}$ && $db_tag =~ ^sha-[0-9a-f]{40}$ ]] || { echo 'Estado inicial sin SHA verificable' >&2; exit 1; }
compose() {
  local release=$1
  shift
  docker compose --project-directory "$root" --env-file "$root/.env" --env-file "$release" -f "$root/compose.prod.yaml" "$@"
}
query_schema() {
  compose "$state/current.env" exec -T db sh -c "exec psql -XAt -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c 'SELECT version_num FROM alembic_version ORDER BY version_num'"
}
ready() {
  curl --fail --silent --show-error --retry 5 --retry-delay 2 --retry-connrefused --max-time 10 http://127.0.0.1:3000/api/health/ready > /dev/null
}
[[ -f $root/compose.prod.yaml && -f $root/scripts/backup.sh ]] || { echo 'Falta composición de producción o script de respaldo' >&2; exit 1; }
compose "$state/current.env" config --quiet
ready
# Confirmar que la imagen DB coincide con el estado; su ciclo de actualización es separado.
db_container=$(compose "$state/current.env" ps -q db)
[[ $(docker inspect --format '{{.Config.Image}}' "$db_container") == "$prefix-db:$db_tag" ]] || { echo 'Imagen DB no coincide con estado aprobado' >&2; exit 1; }
# No recuperar una versión distinta de la que efectivamente está ejecutándose.
for service in api web; do
  container=$(compose "$state/current.env" ps -q "$service")
  [[ -n $container && $(docker inspect --format '{{.Config.Image}}' "$container") == "$prefix-$service:$previous_tag" ]] || { echo 'Release registrado no coincide con API/web activos' >&2; exit 1; }
done
schema_before=$(query_schema)
next=$(mktemp "$state/next.XXXXXX.env")
printf 'IMAGE_PREFIX=%s\nIMAGE_TAG=sha-%s\nPOSTGRES_IMAGE_TAG=%s\n' "$prefix" "$sha" "$db_tag" > "$next"
changed=false
rollback() {
  local code=$?
  trap - EXIT
  if [[ $code != 0 && $changed == true ]]; then
    echo 'Despliegue fallido: verificando compatibilidad antes de recuperar API/web' >&2
    if [[ $(query_schema) == "$schema_before" ]]; then
      if compose "$state/current.env" up -d --no-deps --wait --wait-timeout 120 api web && ready; then
        echo 'Release anterior recuperado; BD y volumen conservados' >&2
      else
        echo 'Recuperación incompleta: intervención administrativa requerida; conservar respaldo' >&2
      fi
    else
      echo 'Esquema cambió: recuperación automática bloqueada; no hacer downgrade ni restaurar sobre datos nuevos' >&2
    fi
  fi
  [[ ! -f $next ]] || rm -- "$next"
  exit "$code"
}
trap rollback EXIT
trap 'exit 130' INT TERM HUP
compose "$next" --profile maintenance pull api web maintenance
# No automatizar migraciones nuevas sin una ventana y plan de compatibilidad.
expected=$(docker run --rm --network none --entrypoint python "$prefix-api:sha-$sha" -c 'from alembic.config import Config; from alembic.script import ScriptDirectory; print("\n".join(sorted(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())))')
[[ $schema_before == "$expected" ]] || { echo 'Migración nueva: requiere aprobación y procedimiento manual antes de CD' >&2; exit 1; }
# Una ventana sin escrituras hace comparable el respaldo y su restauración.
changed=true
compose "$state/current.env" stop web api
(
  cd "$root"
  export COMPOSE_FILE="$root/compose.prod.yaml" IMAGE_PREFIX="$prefix" IMAGE_TAG="$previous_tag" POSTGRES_IMAGE_TAG="$db_tag"
  bash "$root/scripts/backup.sh" --verify
)
compose "$next" --profile maintenance run --rm --no-deps maintenance
compose "$next" --profile maintenance run --rm --no-deps maintenance python -m scripts.db_privileges
[[ $(query_schema) == "$schema_before" ]] || { echo 'El esquema cambió inesperadamente' >&2; exit 1; }
compose "$next" up -d --no-deps --wait --wait-timeout 120 api web
ready
[[ $(compose "$state/current.env" ps -q db) == "$db_container" ]] || { echo 'La identidad del contenedor DB cambió; revisar antes de continuar' >&2; exit 1; }
# Persistir estado solo después de salud correcta; no tocar la configuración privada.
cp "$state/current.env" "$state/previous.env"
mv -- "$next" "$state/current.env"
changed=false
echo "Despliegue saludable: sha-$sha; PostgreSQL conservado"
