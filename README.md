# MediNet-Core · PAB — v0.5

**Evaluación 02 de Desarrollo Seguro — Módulo 6: Pabellones y Quirófanos.**

Proyecto académico con **datos únicamente ficticios**. Esta versión combina la etapa 0.4 (backend reforzado) y 0.5 (CI/CD). La próxima y última versión será la **v1.0**, que incluirá despliegue AWS Academy Learner Lab e informe ISO 27034.

## Diseño e infraestructura

- `web`: React + Vite compilado; Nginx sin root. Panel renovado de control de pabellones, calendario, estados y programación; las cifras provienen de la API, no son métricas inventadas.
- `api`: FastAPI + Swagger /docs, JWT, Argon2id, permisos (admin, coordinator, viewer), validación de horarios y bloqueos PostgreSQL por recurso.
- `db`: PostgreSQL 17-alpine, red interna y volumen persistente.
- `migrations`: revisiones Alembic. Reconoce v0.3 e inicializa el control de versión sin borrar datos si el esquema es compatible.
- `.github/workflows/ci-cd.yml`: jobs de pruebas SQLite + PostgreSQL (incluye dos reservas concurrentes), compilación React, Bandit, pip-audit, Trivy y publicación de imágenes SHA en GHCR. Despliegue hacia EC2 preparado pero **desactivado hasta v1.0**.

> **No está listo para exposición pública ni para datos reales.** Faltan HTTPS y pruebas operativas en EC2, integración con otros módulos y evidencia del pipeline en GitHub. Nunca conectar pacientes reales a esta demostración.

## 1. Actualizar desde v0.3 en Linux Mint (sin perder los datos)

### Primero, respaldo

Abre la terminal en VS Code dentro de tu proyecto **que funciona**:

```bash
cd ~/Escritorio/medinet-pab
# Respaldar PostgreSQL en carpeta privada del usuario; no subir a GitHub.
mkdir -p "$HOME/respaldos-medinet"
chmod 700 "$HOME/respaldos-medinet"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$HOME/respaldos-medinet/pab-antes-v05.sql"
# Respaldar archivos para poder volver a v0.3 si fuese necesario.
cd ~/Escritorio
cp -a medinet-pab medinet-pab-respaldo-v03
```

Guarda el ZIP descargado `medinet-pab-v0.5.zip` en `~/Descargas` y verifica que exista:

```bash
ls -lh ~/Descargas/medinet-pab-v0.5.zip
```

### Actualizar código y volver a iniciar

```bash
cd ~/Escritorio
unzip -o ~/Descargas/medinet-pab-v0.5.zip
cd medinet-pab
# Tu .env no se incluye en el ZIP ni debería reemplazarse.
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

**No uses `docker compose down -v`, `docker volume rm`, ni elimines la carpeta actual.** La base de datos de Docker se mantiene si conservas el nombre del proyecto (`medinet-pab`) y el volumen `postgres_data`.

Si el API no inicia, consulta la migración:

```bash
docker compose logs --tail=100 api
```

No borres la base: si detecta un esquema v0.3 incompatible, la migración se detiene para que lo revisemos antes de tocar registros.

### Si falla la configuración de `.env`

Compose necesita un `.env` en la raíz del proyecto, o uno indicado mediante
`docker compose --env-file /ruta/privada/.env config --quiet`. La plantilla
`.env.example` no se carga automáticamente y deja los secretos vacíos a propósito.

| Variable | Uso local | Producción | Al actualizar desde v0.3 |
|---|---|---|---|
| `POSTGRES_USER` | Obligatoria | Obligatoria | Conservar el usuario existente |
| `POSTGRES_DB` | Obligatoria | Obligatoria | Conservar la base existente |
| `POSTGRES_PASSWORD` | Obligatoria | Obligatoria | Conservar la contraseña existente |
| `JWT_SECRET` | Obligatoria, mínimo 32 caracteres | Obligatoria, mínimo 32 caracteres | Conservar la clave; generar solo si falta |
| `IMAGE_PREFIX`, `IMAGE_TAG` | No se usan | Obligatorias | Identifican las imágenes publicadas por CI |
| `DB_HOST` | Compose fija `db` | Compose fija `db` | No requiere una entrada en `.env` |

Si actualizas una instalación, recupera el `.env` anterior desde tu respaldo.
**No lo reemplaces con `.env.example` ni generes otra contraseña de PostgreSQL**:
las variables `POSTGRES_*` inicializan un volumen vacío y no cambian las
credenciales almacenadas en un volumen existente. Conserva también el nombre
del proyecto y del volumen. Si has perdido el archivo pero los contenedores
siguen funcionando, sus variables permiten recuperarlo localmente; no compartas
la salida de `docker inspect` ni de `docker compose config` sin `--quiet`.

Solo para una instalación nueva, crea la plantilla sin sobrescribir archivos:

```bash
(umask 077; set -C; cat .env.example > .env)
```

Completa los valores en tu editor local. Para secretos con `$` o `#`, usa comillas
simples para conservar el valor literal. Protege el archivo con `chmod 600 .env`.
Las variables exportadas en la terminal prevalecen sobre `.env`; evita valores
antiguos en la sesión al validar o iniciar servicios.

```bash
docker compose config --quiet
# Solo con IMAGE_PREFIX e IMAGE_TAG configuradas; archivo independiente:
docker compose -f compose.prod.yaml config --quiet
```

Esta validación comprueba la configuración, pero no verifica la contraseña
contra PostgreSQL ni la longitud de `JWT_SECRET`; la API exige esta última al
iniciar. Para comprobar servicios ya activos sin reiniciarlos, usa
`docker compose ps` y `curl --fail http://localhost:3000/api/health/ready`.

## 2. Abrir el proyecto

- Panel: **http://localhost:3000**
- Swagger (local): **http://localhost:8000/docs** o **http://localhost:3000/docs**.
- Health de servicios: **http://localhost:3000/api/health/ready**.

**Conserva tu usuario `admin` y su contraseña de v0.3**. Si no existe, créalo únicamente una vez:

```bash
docker compose exec -it api python -m scripts.create_user admin admin
```

Si necesitas datos ficticios:

```bash
docker compose exec api python -m scripts.seed_demo
```

La carga requiere PostgreSQL real. Agrega PAB-01 a PAB-08, 15 pacientes y
10 profesionales claramente ficticios, y hasta 12 cirugías de demostración
(10 programadas y dos en curso). En una base vacía deja cuatro salas disponibles,
dos ocupadas, una en sanitización y una en mantención. Las programadas se sitúan
el día siguiente a la primera carga, según `America/Santiago`.

Antes de cargar en una base persistente, realiza el respaldo de la sección 1.
El script conserva los códigos/referencias existentes, sus valores y todos los
usuarios. Se puede repetir: reconoce las cirugías por su marcador `DEMO-V05` y
no duplica ni actualiza registros, incluso si sus estados cambiaron. Los
horarios existentes no se desplazan; la carga comprueba sala, paciente y equipo
médico, busca otro intervalo o informa que omitió un ejemplo. La operación
completa usa una transacción y los mismos bloqueos de recursos que la API.

La segunda ejecución no renueva fechas antiguas. Para una nueva presentación
puedes programar cirugías adicionales desde el panel. Consulta
[la verificación de datos e interfaz](docs/DEMO_V05_VERIFICACION.md) para los
conteos cargados, evidencias y pendientes de seguridad antes de AWS.

## 3. Trabajar con GitHub desde VS Code

Abre la carpeta `medinet-pab` en VS Code. Revisa el panel de **Control de código fuente** y comprueba que el `.env` no figure entre los cambios:

```bash
git check-ignore -v .env
git ls-files .env
```

El segundo comando no debe devolver nada. Luego confirma el commit desde VS Code con el mensaje **`MediNet PAB v0.5 - CI/CD y seguridad`** y presiona **Sync Changes** para publicarlo en el mismo repositorio privado. No inicialices otro repositorio.

En **GitHub → repositorio → Actions**, revisa el workflow **MediNet PAB - Calidad, seguridad y entrega**. Los primeros jobs pueden requerir descarga de dependencias o exponer hallazgos del escaneo que deban corregirse; no se consideran aprobados hasta que se ejecuten allí correctamente.

## 4. Qué ejecuta el pipeline

| Job | Qué demuestra |
|---|---|
| `backend-and-postgres` | Pruebas Python, acceso y bloqueo, PostgreSQL real, reserva simultánea, migraciones |
| `frontend` | Instalación npm, compilación React, análisis dependencias de producción |
| `sast-sca` | Bandit código Python, pip-audit dependencias |
| `image-scan` | Builds Docker backend/web y Trivy HIGH/CRITICAL |
| `publish` | Solo `push` a `main`: imágenes GHCR con etiqueta `sha-<commit>` |
| `deploy-ec2` | Preparado, **no activo** hasta configurar EC2 y la variable `ENABLE_EC2_DEPLOY=true` |

La publicación de imágenes es independiente de la configuración AWS Academy. Para habilitar despliegue debemos primero crear EC2, TLS, el directorio protegido `/opt/medinet-pab`, un runner confiable con etiqueta `medinet-ec2`, permisos correctos y el `.env` de producción. **No actives esa variable todavía.**

## 5. Pruebas locales

Con Python 3.12, en el directorio raíz:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Sin `TEST_DATABASE_URL`, la prueba concurrente de PostgreSQL se omite de forma explícita. Para ejecutarla en un PostgreSQL de prueba **independiente**, se utiliza esa variable con una DB de pruebas vacía; **la prueba elimina tablas del esquema**, por lo que **jamás** uses tu base de datos real. El CI crea automáticamente una base desechable `medinet_ci` para ello.

Para revisar migración sin manipular datos de tu entorno:

```bash
docker compose exec api alembic current
```

## 6. Criterios que faltan para v1.0

- Despliegue real en EC2 de AWS Academy Learner Lab (`Start Lab`), SG mínimos, HTTPS y disponibilidad operativa.
- Runner de entrega, publicación web y evidencia de pipeline con éxito, además de prueba y verificación desde un equipo externo.
- Informe técnico formal: diagramas de arquitectura y BD, aplicación ISO 27034, matriz de OWASP Top 10, decisiones de hardening y capturas de pruebas reales.
- Corrección de cualquier hallazgo que el pipeline reporte en las imágenes y las dependencias.

Consulta `docs/CHECKLIST_RUBRICA.md`, `docs/SEGURIDAD.md` y `docs/ARQUITECTURA.md`.
