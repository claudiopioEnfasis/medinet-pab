# MediNet-Core · PAB — v0.5

Evaluación 2 de Desarrollo Seguro. Módulo 6: Pabellones y Quirófanos.
Solo datos ficticios. React/Vite + Nginx, FastAPI/JWT/Argon2id, PostgreSQL 17.11
con SQLAlchemy y Alembic. Tres servicios persistentes; el servicio con perfil
`maintenance` se ejecuta únicamente para tareas administrativas puntuales.

La [entrega técnica para Matías](docs/ENTREGA_TECNICA_V05.md) describe la
arquitectura, operación, AWS Academy e informe académico. La
[auditoría integral](docs/AUDITORIA_INTEGRAL_V05.md) distingue resultados actuales,
evidencia histórica y pendientes. HTTPS y la ejecución real de Actions/EC2
siguen pendientes: esta versión permanece local y no admite datos clínicos reales.

## Instalación nueva desde GitHub

Requisitos: Git, Docker Engine/Compose v2 reciente con `env_file.required`, Bash,
Python 3 y OpenSSL en el host. El frontend y backend se compilan dentro de Docker.
Usar Linux/AMD64, o validar expresamente otra arquitectura.

```bash
git clone https://github.com/claudiopioEnfasis/medinet-pab.git
cd medinet-pab
# Solo si NO hay .env: crea archivo privado y nunca lo sobrescribe.
(umask 077; set -C; cat .env.example > .env)
```

Completar `.env` en el editor con un usuario administrador nuevo, nombre de base,
contraseña PostgreSQL aleatoria y JWT_SECRET aleatorio. Generar ambos secretos
por separado con `openssl rand -hex 32`; no copiarlos a capturas ni al informe.
La plantilla contiene secretos vacíos. Conservar `.env` existente al actualizar.

```bash
chmod 600 .env
docker compose config --quiet
docker compose build
docker compose up -d --wait db
# Alembic usa administración, fuera del proceso de la API.
docker compose --profile maintenance run --rm maintenance
# Respaldo verificable ANTES de crear el rol y cambiar privilegios.
bash scripts/backup.sh --verify
# Crea medinet_runtime y .env.runtime (0600), sin sobrescribir .env.
bash scripts/provision_runtime.sh
docker compose up -d --wait
docker compose ps
# Crea usuario de aplicación; solicita la contraseña sin mostrarla.
docker compose --profile maintenance run --rm maintenance python -m scripts.create_user admin admin
# Opcional, solo datos de demostración; transaccional e idempotente.
docker compose exec -T api python -m scripts.seed_demo
```

La API usa exclusivamente la conexión restringida de `.env.runtime` y la clave
JWT de `.env`. El administrador de BD queda en `db` y en los contenedores
transitorios de mantenimiento. El rol runtime no puede ejecutar Alembic,
crear usuarios, cambiar roles ni eliminar registros. Nunca ejecutar
`create_user` dentro de `api` después de la separación.

El seed nuevo genera ocho pabellones, quince pacientes, diez profesionales y
hasta doce cirugías. La instalación anterior contiene trece cirugías; la
adicional se conserva. Repetir el seed no renueva fechas ni reemplaza registros.

## Actualizar esta instalación existente

No clonar encima del repositorio actual, no reinicializar Git, no reemplazar
`.env`, no cambiar contraseñas de un volumen inicializado mediante variables,
no eliminar datos ni volúmenes. **No ejecutar `docker compose down -v`.**

La separación ya se aplicó a esta instalación local con autorización y respaldo
verificado; `.env.runtime` debe conservarse. Los tres servicios están saludables.
La contraseña administrativa anterior permanece pendiente de rotación coordinada.

Antes de aplicar la separación de roles a **otra** instalación existente, revisar y
autorizar el [plan PostgreSQL](docs/PLAN_POSTGRES_V05.md). Generar un nuevo respaldo
con `bash scripts/backup.sh --verify`. Construir las imágenes y ejecutar Alembic
con `maintenance`; ejecutar `provision_runtime.sh` una sola vez si todavía no
existen el rol ni el archivo runtime. Solo entonces recrear la API. Hasta completar
ese paso, no usar la nueva composición para reiniciar el backend anterior.

Si `.env.runtime` ya existe, conservarlo. Después de cada migración:

```bash
docker compose --profile maintenance run --rm maintenance
docker compose --profile maintenance run --rm maintenance python -m scripts.db_privileges
docker compose up -d --wait
```

Los grants son explícitos: una tabla nueva requiere revisar
[scripts/db_privileges.py](scripts/db_privileges.py). El usuario administrador y
las contraseñas de aplicación anteriores se conservan. La rotación de la
contraseña administrativa debe coordinar `ALTER ROLE` con actualización del
archivo privado, después de verificar respaldo y acceso alternativo.

## Acceso y verificación

- Panel: http://localhost:3000
- Swagger: http://localhost:3000/docs (Try it out usa `/api`).
- API directa local: http://localhost:8000/docs
- Readiness: http://localhost:3000/api/health/ready

```bash
curl --fail http://localhost:3000/api/health/ready
docker compose exec -T web nginx -t
docker compose --profile maintenance run --rm maintenance python -m alembic current
docker compose --profile maintenance run --rm maintenance python -m alembic check
```

Roles de la aplicación: `admin` administra catálogos y cirugías; `coordinator`
programa y cambia estados; `viewer` consulta. Sesión JWT de treinta minutos en
memoria del navegador. No se guarda en localStorage ni sessionStorage.

## Pruebas y seguridad

Con Python 3.12 y soporte `venv/ensurepip` instalado:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Para ejecutar **toda** la suite, configurar `TEST_DATABASE_URL` mediante un
archivo privado o variable de entorno que apunte a PostgreSQL **desechable**,
con base terminada en `_test` o `_ci`. Nunca apuntar a la instalación real:
las pruebas existentes crean y eliminan tablas de prueba. Los nuevos ensayos de
privilegios crean una base aislada y roles sin tocar usuarios de la aplicación
real, por lo que el usuario de pruebas requiere administración en ese clúster.
Sin la variable, las pruebas PostgreSQL se omiten explícitamente; no equivale a
la validación completa. CI prepara un clúster temporal automáticamente.

Controles: Bandit (`app scripts`), pip-audit (runtime, desarrollo y navegador), `npm audit`
con dependencias de desarrollo, actionlint, ShellCheck y Trivy de las tres
imágenes, sin omitir avisos sin corrección. Las instrucciones y resultados están
en la entrega técnica. Las pruebas del navegador se ejecutan únicamente contra
una copia con usuarios ficticios y confirmación explícita de escritura.

## Respaldo y recuperación

```bash
bash scripts/backup.sh --verify
```

Genera un directorio privado `backups/`, ignorado por Git y Docker: dump custom,
roles globales, SHA-256 y comparación de todas las filas tras restaurar en otro
PostgreSQL sin red. No detiene ni reemplaza la base original. Si hay escrituras
simultáneas, la comparación puede diferir: repetir en ventana sin escrituras.
El contenedor de verificación se detiene; no se elimina ningún volumen.

No publicar dumps ni `globals.sql`: contienen datos y hashes de contraseñas.
Guardar otra copia cifrada fuera de la instancia y ensayar recuperación antes
de producción. La recuperación sobre datos existentes exige revisión y
aprobación; no ejecutar restauraciones destructivas de forma automática.

## GitHub Actions y EC2

La [guía CI/CD](docs/GITHUB_ACTIONS_CICD.md) documenta Build, Test PostgreSQL
sin omisiones, Security Scan, publicación GHCR por SHA y despliegue SSH restringido
en un workflow separado. No requiere runner self-hosted ni credenciales AWS.

La revisión local aprobó 76 pruebas. Existe una ejecución remota exitosa del
commit anterior; estos cambios todavía requieren push autorizado y una nueva
validación remota. EC2 permanece deshabilitado, pendiente de preparación,
protecciones de GitHub disponibles según el plan, HTTPS y prueba real de entrega.
