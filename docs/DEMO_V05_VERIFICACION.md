# MediNet PAB v0.5: datos y verificación de la presentación

Fecha: 30 de octubre de 2026, America/Santiago. API activa: **0.5.0**.

## Datos PostgreSQL finales

| Registro | Cantidad |
|---|---:|
| Pabellones PAB-01 a PAB-08 | 8 |
| Pacientes ficticios DEMO-P01 a DEMO-P15 | 15 |
| Profesionales ficticios DEMO-M01 a DEMO-M10 | 10 |
| Cirugías | 13 |
| Usuarios originales conservados | 1 |

Pabellones: cuatro disponibles, dos ocupados, uno en sanitización y uno en
mantención. Cirugías: diez programadas, dos en curso y una finalizada. Hay
intervenciones electivas y de urgencia. El seed creó doce; la decimotercera,
identificada como `DEMO-UI-V05`, se programó y finalizó desde React.
La comprobación de todas las reservas activas encontró **cero solapamientos**
que compartieran pabellón, paciente o integrante del equipo médico.

Los nombres/referencias se identifican explícitamente como ficticios y no
incluyen RUN, teléfonos, correos ni historias clínicas reales.

## Respaldo y conservación

Antes de escribir datos persistentes se detuvieron API y web y se creó un nuevo
respaldo privado en:

```text
/home/midnight/respaldos-medinet/demo-v05-20261030T043016/
```

Contiene `database.dump`, `globals.sql`, `SHA256SUMS`, inventario del archivo y
logs de verificación. La carpeta tiene permisos `0700`; los respaldos, `0600`.
No deben compartirse ni incorporarse a Git. Se verificó el archivo mediante
`pg_restore --list`, restauración real en PostgreSQL 17 temporal y comparación
íntegra de las seis tablas con el origen. Sobre esa copia se ensayaron también
Alembic y dos ejecuciones del seed.

La base original tenía un usuario y ninguna sala, paciente, médico o cirugía.
El registro completo de usuarios, incluidos rol, estado y hash de contraseña,
coincide al final con el respaldo. No se crearon ni modificaron usuarios en la
instalación. `.env` coincide byte por byte con el archivo inicial. Se conservó
el volumen `medinet-pab_postgres_data`; no se ejecutó ningún borrado de volúmenes.

## Seed repetible

```bash
docker compose exec -T api python -m scripts.seed_demo
```

`scripts/seed_demo.py` requiere PostgreSQL. Solo agrega recursos ausentes y no
actualiza registros previos. Usa las validaciones `SurgeryCreate`, la misma
comprobación triple de conflictos de la API y sus mismos bloqueos transaccionales.
El helper de bloqueos se comparte en `app/locking.py`, conservando exactamente
las claves de la versión anterior. La adquisición del conjunto completo de
recursos en orden global evita ciclos al reservar varias salas en una carga.
Un bloqueo adicional serializa dos ejecuciones del seed.

La operación se confirma en una única transacción. Un fallo revierte todas sus
inserciones. Los marcadores `DEMO-V05-01` a `DEMO-V05-12` identifican las cirugías
ya creadas sin depender del día o del estado posterior. Si un recurso previo no
está disponible, el script busca un horario compatible o informa la omisión.

La segunda ejecución sobre la base original produjo cero inserciones y ninguna
modificación. Una tercera ejecución, después de utilizar la interfaz, también
conservó íntegramente los trece registros de cirugía y todos los demás datos.
No se renuevan automáticamente fechas ni estados de ejemplos ya existentes.

## Pruebas y frontend

La suite ejecutó **40 pruebas: 40 aprobadas y ninguna omitida**. Incluye las 33
anteriores y siete nuevas: carga completa, repetición al día siguiente,
conservación de registros/usuarios, disponibilidad triple, reversión completa,
dos seeds concurrentes y rechazo de una conexión SQLite para la carga.
Las pruebas del seed que escriben datos usan esquemas independientes en un
PostgreSQL 17 temporal. La prueba de dos reservas simultáneas produjo 201 y 409.
Los controles de autenticación y permisos de la suite anterior siguen aprobados.

En Chromium se comprobó la instalación desplegada en `http://localhost:3000`:

1. Dashboard con las ocho tarjetas PAB-01 a PAB-08 y los cuatro estados.
2. Selección de paciente y equipo ya cargados y consulta de disponibilidad.
3. Programación de una cirugía de urgencia desde el formulario: 201.
4. Rechazo de su duplicado en la API real: 409.
5. Consulta en la agenda y filtro de búsqueda.
6. Inicio y finalización de la cirugía desde sus botones de React.
7. Cambio de estado del pabellón y cierre de sesión.

No hubo errores JavaScript de página. Se utilizó una sesión técnica firmada de
diez minutos, con autorización del administrador existente, sin pedir ni cambiar
su contraseña. La respuesta de login se preparó para esa sesión de prueba; todas
las consultas y operaciones posteriores utilizaron la API y PostgreSQL reales.
Esto no sustituye una comprobación manual de la contraseña original.

Evidencia: [dashboard-v05.png](evidencias/dashboard-v05.png).

Los tres servicios quedaron `healthy`, con cero reinicios y sin
ERROR/FATAL/CRITICAL/PANIC ni trazas de excepciones en los logs revisados.
`/health/ready`, el proxy, Swagger, `nginx -t` y Compose funcionan. Alembic
permanece en `0001 (head)` y `alembic check` no detecta diferencias. La carga no
requiere una migración nueva. El PostgreSQL temporal se retira al terminar.

## Git y preparación para el repositorio original

La carpeta actual **no contiene un repositorio Git utilizable**. `git status`,
`git remote -v`, la rama activa y el historial no pueden consultarse aquí. No se
inicializó otro repositorio ni se modificó un historial.

URL indicada por el usuario: `https://github.com/claudiopioEnfasis/medinet-pab`.
La conexión GitHub devolvió 404 y la consulta Git por HTTPS requirió credenciales
no disponibles. Esto puede corresponder a un repositorio privado sin autorización;
no demuestra que el repositorio no exista. No se pudo confirmar el remoto, la
rama predeterminada ni el historial de ese repositorio.

Se verificaron las exclusiones con metadatos Git temporales externos a esta
carpeta. Se excluyen `.env`, variantes privadas, claves, credenciales AWS y
respaldos. El lockfile de React sí queda permitido. La búsqueda local no halló
credenciales activas incrustadas en el código; una coincidencia parcial dentro
del alfabeto de validación de usuarios se descartó como incidental.
Sin el clon original no puede certificarse el contenido de commits anteriores.

Se prepara una entrega de fuentes sin `.env`, secretos, respaldos, `.git`,
entornos virtuales ni dependencias instaladas en:

```text
/home/midnight/entregas-medinet/medinet-pab-v0.5-demo-20261030T043016.tar.gz
```

Incluye un manifiesto SHA-256; junto al archivo se entrega su suma de integridad.
Debe revisarse e integrarse en el clon original, comprobando primero que `origin`
corresponda a la URL indicada y que los cambios locales de ese clon se conserven.
No se preparó un commit contra una base desconocida y no se hizo push.

## Pipeline CI/CD

| Etapa | Configuración revisada | Comprobación local |
|---|---|---|
| Test | Python 3.12 y PostgreSQL 17; suite completa; Alembic y seed repetido | 40 pruebas y ensayo real aprobados |
| Build | React y dos imágenes Docker multi-stage | Ambos builds aprobados |
| SAST | Bandit en app y scripts | Aprobado |
| SCA | pip-audit y npm audit de producción | npm aprobado; pip-audit con hallazgos |
| Vulnerabilidades de imagen | Trivy HIGH/CRITICAL con corrección disponible | Hallazgos en ambas imágenes |
| Publicación | GHCR por SHA, después de todos los controles, solo push a main | Requiere GitHub y sus permisos; no se ejecutó |
| Deployment | EC2, runner self-hosted y environment production | Preparado y condicionado a ENABLE_EC2_DEPLOY=true; no activado |

`actionlint` validó la sintaxis, expresiones, dependencias entre jobs y scripts.
Se declaró la etiqueta personalizada `medinet-ec2` en `.github/actionlint.yaml`.
Se comprobó la existencia de las etiquetas públicas utilizadas por checkout,
setup-python, setup-node, build-push-action y trivy-action.
La ejecución real de GitHub Actions y sus permisos solo pueden confirmarse en
el repositorio autorizado.

La compilación frontend usa ahora `package-lock.json` y `npm ci`, tanto en Docker
como en CI. La entrega EC2 valida Compose y espera contenedores saludables antes
del chequeo HTTP, conservando el `.env` del servidor. No elimina volúmenes.

**Los controles de seguridad no están aprobados para AWS.** La auditoría del
runtime Python reportó 37 entradas en tres paquetes (incluye pip y avisos
duplicados). Trivy reportó ocho HIGH y un CRITICAL para API y 46 HIGH y un
CRITICAL para web, con el mismo filtro del pipeline. Estos números son entradas
de hallazgo, no necesariamente CVE únicas. No se ocultaron fallos ni se rebajaron
umbrales. Véase [el detalle de seguridad](SEGURIDAD_V05_RESULTADOS.md).

## Archivos cambiados en esta tarea

- `scripts/seed_demo.py`, `app/locking.py`, `app/main.py`.
- `tests/test_seed_demo.py`.
- `compose.yaml`, `compose.prod.yaml`.
- `.github/workflows/ci-cd.yml`, `.github/actionlint.yaml`.
- `frontend/Dockerfile`, `frontend/package-lock.json`, `frontend/.dockerignore`.
- `.gitignore`, `.dockerignore`, `README.md`.
- `docs/DEMO_V05_VERIFICACION.md`, `docs/SEGURIDAD_V05_RESULTADOS.md`.
- `docs/DESPLIEGUE_LOCAL_V05.md`: enlace al estado posterior.
- `docs/evidencias/dashboard-v05.png`, `docs/evidencias/seguridad-v05.json`.

## Pendientes antes de AWS Academy / v1.0

1. Actualizar las dependencias e imágenes afectadas y repetir SCA/Trivy y regresión.
2. Recuperar acceso al clon/repositorio original e integrar la entrega conservando
   historial y cambios del equipo. Ejecutar Actions allí y resolver sus fallos.
3. Configurar EC2 de AWS Academy, HTTPS, red y reglas de acceso, runner confiable,
   permisos GHCR y environment production, respaldos y retorno a versión anterior.
4. Habilitar el deployment solo después de esos controles y obtener evidencia
   real del despliegue y la disponibilidad externa.
5. Completar el informe y las evidencias de la rúbrica/ISO 27034. La suite conserva
   un aviso de deprecación de Starlette/AnyIO, sin fallos funcionales.
