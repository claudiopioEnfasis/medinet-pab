#!/usr/bin/env bash
# Ejecutar después de respaldar y migrar. Nunca sobrescribe .env ni .env.runtime.
set -euo pipefail
set +x
umask 077
compose_file=${1:-compose.yaml}
# config contiene secretos: se consume por pipe y solo sale el nombre de BD.
database=$(docker compose -f "$compose_file" --profile maintenance config --format json | python3 -c '
import json, sys
name = json.load(sys.stdin)["services"]["maintenance"]["environment"]["POSTGRES_DB"]
if not name.replace("_", "").isalnum():
    raise SystemExit("Nombre de base no admitido")
print(name)
')
runtime_password=$(openssl rand -hex 32)
# noclobber: reservar el archivo antes de CREATE ROLE, aun frente a dos procesos.
(set -o noclobber; printf 'POSTGRES_USER=medinet_runtime\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=%s\n' "$runtime_password" "$database" > .env.runtime)
printf '{"password":"%s"}\n' "$runtime_password" | docker compose -f "$compose_file" --profile maintenance run --rm --no-deps -T maintenance python -m scripts.db_privileges --create
unset runtime_password
printf 'Rol runtime creado; archivo privado .env.runtime preparado; .env intacto.\n'
