# Despliegue local de MediNet PAB v0.5

Fecha: 30 de octubre de 2026, America/Santiago.

**Estado posterior:** se cargaron y verificaron los datos de demostración.
Consulta [la verificación de la presentación](DEMO_V05_VERIFICACION.md), que
actualiza los conteos, pruebas y resultados de seguridad de este informe inicial.

## Resultado

La instalación local sirve **API v0.5.0**, frontend React v0.5 y PostgreSQL 17.
Se reconstruyeron las imágenes API/web y se recrearon los tres contenedores.
PostgreSQL reutiliza su imagen y el mismo volumen persistente; no tiene un
Dockerfile propio que reconstruir.

| Componente | Estado comprobado |
|---|---|
| API | Activa; OpenAPI directo y mediante Nginx declara `0.5.0` |
| Frontend | React renderiza y sirve la interfaz v0.5 |
| PostgreSQL | Saludable; mismo volumen `medinet-pab_postgres_data` |
| Alembic | `0001 (head)`; sin diferencias de esquema en `alembic check` |
| Datos anteriores | Las seis tablas conservan todos sus valores originales |
| Administrador original | Un administrador activo, sin bloqueo; hash de contraseña conservado |
| Registros de servicios | Sin ERROR/FATAL/CRITICAL/PANIC/Traceback; cero reinicios |

## Respaldo verificado

Ruta privada, fuera del proyecto:

```text
/home/midnight/respaldos-medinet/v05-20261030T040153/
```

Contenido relevante:

- `database.dump`: respaldo completo de la base en formato custom de PostgreSQL.
- `globals.sql`: roles PostgreSQL; contiene material sensible y debe mantenerse privado.
- `SHA256SUMS`: verificaciones de integridad de los archivos del respaldo.
- `archive-list.txt`: inventario validado con `pg_restore --list`.
- `before.json` y `verification.json`: conteos y evidencia de comparación.
- Logs privados del ensayo, migración, pruebas y servicios desplegados.
- `previous-api/` y `previous-web/`: archivos de la aplicación anterior conservados.

La carpeta tiene permisos `0700` y los archivos de respaldo/verificación `0600`.
Los datos y los hashes de contraseñas del respaldo son privados: no deben
adjuntarse al repositorio ni publicarse.

Para comprobar nuevamente la integridad, sin mostrar el contenido del respaldo:

```bash
cd /home/midnight/respaldos-medinet/v05-20261030T040153
sha256sum --check SHA256SUMS
```

Se detuvieron API y web antes de respaldar para evitar escrituras de aplicación
durante la comparación. PostgreSQL permaneció disponible. El archivo se restauró
con `pg_restore --exit-on-error --single-transaction --no-owner --no-acl` en una
base temporal de PostgreSQL 17. Se compararon conteos y huellas de todas las
filas de las seis tablas, incluidos todos los campos de usuarios. La copia
restaurada coincidió íntegramente con el origen. Las sumas SHA-256 se verificaron
nuevamente al terminar.

Conteos preservados: `app_users=1`; `operating_rooms=0`, `patients=0`,
`medical_staff=0`, `surgeries=0`, `surgery_staff=0`.

## Migración y despliegue

Se revisaron `scripts/migrate.py`, `migrations/env.py` y la revisión inicial
`0001`. Primero se ensayó la actualización sobre el respaldo restaurado,
utilizando la imagen nueva y una conexión aislada de producción. Pasaron tanto
la migración como `alembic check`.

Después se recreó el contenedor PostgreSQL conservando el volumen y se ejecutó
la migración original mediante un contenedor de una sola ejecución:

```bash
docker compose run --rm --no-deps --entrypoint python api -m scripts.migrate
docker compose run --rm --no-deps --entrypoint alembic api check
docker compose run --rm --no-deps --entrypoint alembic api current
```

El esquema v0.3 ya coincidía con el baseline: se registró `0001` y se verificó
`head`, sin recrear las tablas existentes. No fue necesaria una revisión
adicional. Se comprobó después que todas las filas conservaban los mismos
valores, incluidos usuario, rol, hash de contraseña y estado de cuenta.

API y web se recrearon con las imágenes v0.5. El arranque del backend ejecutó
nuevamente su migración idempotente antes de Uvicorn. No falló ninguna migración.
Las comprobaciones finales confirmaron el mismo volumen, contenedores nuevos y
el `.env` idéntico byte por byte al inicial, con permisos `0600`.

## Validación funcional

| Prueba | Resultado |
|---|---|
| `docker compose config --quiet` | Correcto |
| Construcción Compose de API y web | Correcta |
| `http://localhost:8000/health/ready` | 200, base disponible |
| `http://localhost:3000/api/health/ready` | 200 a través del proxy |
| `/openapi.json` directo y mediante Nginx | API `0.5.0` |
| `/docs` directo y mediante Nginx | 200; Swagger renderizado con operaciones visibles en navegador |
| Web React desplegada | Pantalla de acceso renderizada, sin errores JavaScript de página |
| `nginx -t` | Correcto |
| Suite backend completa | **33 pasaron, ninguna omitida** |
| Dos reservas concurrentes en PostgreSQL real | Respuestas **201 y 409** |
| Login de administrador temporal desde navegador | Correcto |
| Dashboard autenticado y alta de pabellón desde React | Correctos |
| Alta de paciente y profesional ficticios desde React | Correcta |
| Disponibilidad y programación desde React | Correctas; cirugía creada con 201 |
| Reserva duplicada | Rechazada con 409 |
| Inicio y finalización de cirugía | Pabellón ocupado y después en sanitización |
| Cambio de estado de pabellón y logout | Correctos |

La suite se ejecutó con `TEST_DATABASE_URL` apuntando exclusivamente a
`medinet_ci` en otro contenedor PostgreSQL, sin montar volúmenes persistentes.
El navegador probó las mismas imágenes desplegadas con una base independiente
`medinet_e2e_test` y un administrador temporal. No se añadieron datos de prueba
ni usuarios a la instalación original. Al finalizar se retiraron los tres
contenedores temporales y su red; sus datos estaban en tmpfs. No se ejecutó
ningún borrado de volúmenes.

## Git, secretos y archivos

Esta carpeta carece de metadatos Git utilizables. No se inicializó un repositorio
nuevo y no se realizó push. Se verificaron las reglas del `.gitignore` mediante
Git con un índice temporal: `.env` y variantes privadas quedan excluidos, mientras
`.env.example` permanece permitido. Se buscaron los secretos activos en los
archivos locales fuera de `.env`; solo apareció una coincidencia parcial dentro
de la lista de caracteres permitidos de `scripts/create_user.py`, sin una
asignación de credenciales. No se imprimieron contraseñas ni tokens.

No se puede certificar si hay secretos en commits anteriores o en un repositorio
remoto sin disponer del repositorio Git correspondiente.

Archivos del proyecto modificados en esta operación:

- `docs/DESPLIEGUE_LOCAL_V05.md`: este informe.
- `docs/REVISION_CONFIG_V05.md`: enlace al estado actualizado.

No fueron necesarios cambios en React, Python, migraciones ni Compose. Se
añadieron herramientas de navegador únicamente al entorno auxiliar `.venv/`.
Los respaldos y diagnósticos permanecen fuera del proyecto.

## Pendientes

- El usuario realizará personalmente el login del administrador original en
  **http://localhost:3000**. Se conservaron sus credenciales y se verificó que la
  cuenta está activa y desbloqueada; no se probó su contraseña ni se cambió.
- Hace falta el repositorio Git original para revisar índice e historial real
  antes de publicar cambios.
- La suite emitió un aviso de deprecación de `BlockingPortal` en Starlette/AnyIO.
  Las 33 pruebas pasaron.
- El frontend continúa sin lockfile; la reproducibilidad de sus dependencias
  transitivas sigue pendiente, según la revisión anterior.
- Esta operación valida el despliegue local. No ejecutó GitHub Actions, escáneres
  de vulnerabilidades, publicación de imágenes ni despliegue AWS.
