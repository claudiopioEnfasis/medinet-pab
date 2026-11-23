#!/usr/bin/env bash
# Bootstrap de un nodo de aplicacion MediNet PAB (EVA 03 - Multi-AZ).
# Generado por Terraform: no editar a mano en la instancia.
set -euo pipefail
exec > >(tee -a /var/log/medinet-bootstrap.log) 2>&1

export DEBIAN_FRONTEND=noninteractive

echo "[1/6] Instalando Docker, Compose v2 y Git"
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl git docker.io docker-compose-v2
systemctl enable --now docker

echo "[2/6] Clonando repositorio en /opt/medinet"
install -d -m 0755 /opt/medinet
if [ ! -d /opt/medinet/.git ]; then
  git clone --depth 1 --branch '${repo_branch}' '${repo_url}' /opt/medinet
fi
cd /opt/medinet

echo "[3/6] Escribiendo variables de entorno del nodo"
umask 077
cat > /opt/medinet/.env <<'MEDINET_ENV'
IMAGE_PREFIX=${image_prefix}
IMAGE_TAG=${image_tag}
DB_HOST=${db_host}
POSTGRES_DB=${db_name}
POSTGRES_USER=${db_user}
POSTGRES_PASSWORD=${db_password}
JWT_SECRET=${jwt_secret}
MEDINET_ENV
chmod 0600 /opt/medinet/.env

if [ -n '${ghcr_token}' ]; then
  echo "[4/6] Autenticando en GHCR"
  printf '%s' '${ghcr_token}' | docker login ghcr.io -u '${ghcr_user}' --password-stdin
else
  echo "[4/6] GHCR sin credenciales (imagenes publicas)"
fi

%{ if run_migrations ~}
echo "[5/6] Aplicando migraciones Alembic contra RDS"
for intento in $(seq 1 20); do
  if docker compose -f compose.aws.yaml --profile maintenance run --rm migrate; then
    echo "Migraciones aplicadas"
    break
  fi
  if [ "$intento" = "20" ]; then
    echo "No fue posible migrar la base tras 20 intentos" >&2
    exit 1
  fi
  echo "Reintento $intento/20 en 15s (RDS aun no disponible)"
  sleep 15
done
%{ else ~}
echo "[5/6] Este nodo no ejecuta migraciones (las aplica el primer nodo)"
%{ endif ~}

echo "[6/6] Levantando API y frontend endurecidos"
docker compose -f compose.aws.yaml up -d --remove-orphans
docker compose -f compose.aws.yaml ps
