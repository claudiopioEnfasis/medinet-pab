#!/usr/bin/env bash
# Bootstrap de un nodo de aplicacion MediNet PAB (EVA 03 - Multi-AZ).
# Generado por Terraform: no editar a mano en la instancia.
set -euo pipefail
exec > >(tee -a /var/log/medinet-bootstrap.log) 2>&1

export DEBIAN_FRONTEND=noninteractive

echo "[1/6] Instalando Docker, Compose v2 y Git"
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl git docker.io docker-compose-v2 unzip
systemctl enable --now docker
umask 077
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
case $(uname -m) in x86_64|aarch64) arch=$(uname -m) ;; *) exit 1 ;; esac
curl --fail --silent --show-error --proto '=https' --retry 3 --max-time 90 \
  "https://awscli.amazonaws.com/awscli-exe-linux-$arch.zip" -o "$tmp/aws.zip"
unzip -q "$tmp/aws.zip" -d "$tmp"
"$tmp/aws/install" --install-dir /opt/medinet/aws-cli --bin-dir /opt/medinet/aws-bin >/dev/null

echo "[2/6] Clonando repositorio en /opt/medinet"
install -d -m 0755 /opt/medinet
if [ ! -d /opt/medinet/.git ]; then
  git clone --depth 1 --branch '${repo_branch}' '${repo_url}' /opt/medinet
fi
cd /opt/medinet

echo "[3/6] Escribiendo variables de entorno del nodo"
runtime_password=$(/opt/medinet/aws-bin/aws ssm get-parameter --region '${aws_region}' \
  --name '${runtime_param}' --with-decryption --query 'Parameter.Value' --output text --no-cli-pager)
if [[ ! "$runtime_password" =~ ^[A-Za-z0-9_-]{48,128}$ ]]; then
  echo 'Formato inválido para la credencial de ejecución' >&2
  exit 1
fi
cat > /opt/medinet/.env <<'MEDINET_ENV'
IMAGE_PREFIX=${image_prefix}
IMAGE_TAG=${image_tag}
DB_HOST=${db_host}
POSTGRES_DB=${db_name}
JWT_SECRET=${jwt_secret}
MEDINET_ENV
printf 'POSTGRES_USER=medinet_runtime\nPOSTGRES_PASSWORD=%s\n' "$runtime_password" >> /opt/medinet/.env
chmod 0600 /opt/medinet/.env

%{ if ghcr_token != "" ~}
  echo "[4/6] Autenticando en GHCR"
  printf '%s' '${ghcr_token}' | docker login ghcr.io -u '${ghcr_user}' --password-stdin
%{ else ~}
  echo "[4/6] GHCR sin credenciales (imagenes publicas)"
%{ endif ~}

%{ if run_migrations ~}
echo "[5/6] Aplicando migraciones Alembic contra RDS"
cat > "$tmp/migrate.env" <<'MEDINET_MIGRATION_ENV'
POSTGRES_USER=${db_user}
POSTGRES_PASSWORD=${db_password}
MEDINET_MIGRATION_ENV
maintenance=(docker compose --env-file .env --env-file "$tmp/migrate.env" -f compose.aws.yaml --profile maintenance run --rm --no-deps -T migrate)
for intento in $(seq 1 20); do
  if "$${maintenance[@]}" >"$tmp/maintenance.log" 2>&1; then
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
# Crear el rol en una instalación nueva o reaplicar permisos al rol existente.
if ! "$${maintenance[@]}" python -m scripts.db_privileges >"$tmp/maintenance.log" 2>&1; then
  if ! printf '{"password":"%s"}\n' "$runtime_password" | \
    "$${maintenance[@]}" python -m scripts.db_privileges --create >"$tmp/maintenance.log" 2>&1; then
    echo 'No se pudo aprovisionar el rol de ejecución' >&2
    exit 1
  fi
fi
rm -f "$tmp/migrate.env" "$tmp/maintenance.log"
%{ else ~}
echo "[5/6] Este nodo no ejecuta migraciones (las aplica el primer nodo)"
%{ endif ~}
unset runtime_password

echo "[6/6] Levantando API y frontend endurecidos"
docker compose -f compose.aws.yaml up -d --remove-orphans
docker compose -f compose.aws.yaml ps
