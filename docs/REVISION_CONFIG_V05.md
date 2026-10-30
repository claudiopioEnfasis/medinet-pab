# Revisión de configuración y proyecto v0.5

Fecha: 30 de octubre de 2026 (America/Santiago).

**Actualización posterior:** el despliegue local v0.5 y la migración real ya se
completaron. Consulta [Despliegue local v0.5](DESPLIEGUE_LOCAL_V05.md) para el
estado vigente, respaldo restaurado y pruebas PostgreSQL. Este documento conserva
los resultados de la revisión inicial, anterior al despliegue.

## Problema y corrección

La copia revisada no tenía `.env`. `docker compose config --quiet` fallaba por
ausencia de `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` y `JWT_SECRET`.
`.env.example` no se carga automáticamente y sus secretos están vacíos.

Se recuperaron las cuatro variables desde los contenedores existentes y se creó
exclusivamente el archivo ausente con permisos `0600`. No se generaron claves
nuevas ni se cambiaron credenciales. Se comprobó en memoria que los valores
interpretados por Compose coinciden exactamente con los originales, sin
imprimirlos. Las variables PostgreSQL coinciden entre los contenedores DB y API;
la clave JWT cumple el mínimo de 32 caracteres.

`compose.yaml` conserva sus variables obligatorias y no necesitó cambios.
`compose.prod.yaml` exige además `IMAGE_PREFIX` e `IMAGE_TAG`; se documentaron
en la plantilla. `DB_HOST=db` se fija en ambos archivos Compose. No se deben
pasar credenciales de backend al frontend.

## Archivos

- `.env`: creado con los valores existentes y permisos privados.
- `.env.example`: requisitos locales, variables de producción y conservación de
  credenciales durante una actualización.
- `.dockerignore`: excluye también variantes `.env.*`, salvo la plantilla.
- `README.md`: diagnóstico, matriz de variables, creación sin sobrescritura,
  prioridad de variables exportadas y validación local/producción.
- `docs/REVISION_CONFIG_V05.md`: este informe.

Se preparó un entorno auxiliar `.venv/` para las pruebas; está contemplado en
`.gitignore` y `.dockerignore`.

## Compatibilidad con la instalación anterior

Se mantiene el proyecto `medinet-pab` y el volumen
`medinet-pab_postgres_data`, montado en `/var/lib/postgresql/data`, con
PostgreSQL 17. Se consultaron únicamente metadatos del esquema y `SELECT 1`.
Las seis tablas de aplicación y sus columnas contienen los nombres requeridos
por `scripts/migrate.py`. La conexión SQL desde la API existente funciona.

Las pruebas de migración comprobaron una base SQLite vacía y una simulación
del esquema anterior con conservación de un registro. La simulación utiliza
los modelos actuales: no equivale a migrar una copia histórica independiente.
El validador automático de baseline comprueba nombres de tablas y columnas;
no demuestra equivalencia de tipos, índices o restricciones de una base antigua.
No se ejecutó ninguna migración sobre PostgreSQL existente.

La API activa declara **v0.3.0** y aún usa el comando de arranque anterior.
La recuperación del entorno no despliega el código v0.5. Por eso el endpoint
`/health/ready`, presente en el código nuevo, devuelve 404 en la instalación
activa. Antes de actualizarla corresponde realizar el respaldo indicado en
README y comprobar después la migración y ese endpoint.

## Pruebas y comprobaciones

| Comprobación | Resultado |
|---|---|
| `docker compose config --quiet` con el entorno recuperado | Correcto |
| `docker compose -f compose.prod.yaml config --quiet` | Correcto con referencias de imagen de prueba; no acredita imágenes publicadas |
| Permisos e interpretación de `.env` | `0600`; valores idénticos a los contenedores |
| Suite Python v0.5 en SQLite temporal | 32 pasaron, 1 omitida |
| Migración inicial y baseline conservando registros en SQLite | Ambas pasaron, incluidas en las 32 |
| Prueba concurrente PostgreSQL | Omitida: no se configuró una base de pruebas independiente |
| Construcción Docker frontend, incluido `npm run build` | Correcta |
| Construcción Docker backend | Correcta |
| `docker compose ps` | API y web activos; DB saludable |
| `nginx -t` en el contenedor activo | Correcto |
| HTTP web y `/api/health` | 200 |
| HTTP `/api/health/ready` y backend `/health/ready` | 404: API activa v0.3.0 |
| `SELECT 1` desde la API activa hacia PostgreSQL | Correcto |

La suite emitió un aviso de deprecación de `BlockingPortal` de Starlette/AnyIO.
El primer intento de pruebas quedó bloqueado en el aislamiento y fue
interrumpido; la ejecución fuera de ese aislamiento completó las 32 pruebas.
Se excluyó explícitamente `TEST_DATABASE_URL` de ambas ejecuciones.

Se crearon imágenes separadas `medinet-pab-api:revision-env-20261030` y
`medinet-pab-web:revision-env-20261030`. Los servicios existentes no se
reconstruyeron, reiniciaron ni reemplazaron. No se eliminaron volúmenes ni datos.

## Alcance adicional y límites

Se revisaron también backend, autenticación, modelos, validaciones, scripts,
migraciones, frontend, proxy Nginx, Dockerfiles, documentación y workflow CI/CD.
El frontend carece de un lockfile de dependencias: usa `npm install` tanto en
Docker como en CI, por lo que las dependencias transitivas pueden cambiar entre
compilaciones. Su compilación actual pasó; la reproducibilidad queda pendiente.

No hay metadatos Git utilizables en esta copia; no se pudo contrastar el código
contra un commit v0.3 ni comprobar el estado de seguimiento real de `.env`.
Las reglas presentes de `.gitignore` sí excluyen los entornos privados.
No se ejecutaron GitHub Actions, publicación, despliegue AWS, Bandit, auditorías
de dependencias ni Trivy; los builds exitosos no certifican esos controles.
