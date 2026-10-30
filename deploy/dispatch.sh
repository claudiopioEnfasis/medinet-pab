#!/usr/bin/env bash
# Instalar como archivo protegido; authorized_keys fuerza exclusivamente este comando.
set -euo pipefail
set +x
umask 077
root=/opt/medinet-pab
[[ ${SSH_ORIGINAL_COMMAND:-} =~ ^deploy\ ([0-9a-f]{40})$ ]] || { echo 'Comando SSH no admitido' >&2; exit 2; }
sha=${BASH_REMATCH[1]}
IFS= read -r registry_user
IFS= read -r registry_token
[[ $registry_user =~ ^[A-Za-z0-9_.-]+$ && -n $registry_token ]] || { echo 'Autorización GHCR ausente' >&2; exit 1; }
auth=$(mktemp -d "$root/.deployment/auth.XXXXXX")
cleanup() { docker --config "$auth" logout ghcr.io > /dev/null 2>&1 || true; rm -rf -- "$auth"; }
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
printf '%s' "$registry_token" | docker --config "$auth" login ghcr.io -u "$registry_user" --password-stdin > /dev/null
unset registry_token
export DOCKER_CONFIG="$auth"
# No shell remoto arbitrario, copia de scripts ni modificación del directorio por la entrada SSH.
bash "$root/deploy/deploy.sh" "$sha" "$root"
