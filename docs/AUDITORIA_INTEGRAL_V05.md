# Auditoría integral MediNet PAB v0.5

30 de octubre de 2026. Repositorio existente, rama `main`, HEAD de partida
`a1d0b4ca08360b9acafda87eb860e61b3fe023a1`.

## 1. Dictamen y alcance

El código candidato funciona en una instalación limpia y en una copia de los
datos originales con PostgreSQL restringido. Se conservaron la arquitectura,
la estética y las funciones de negocio. **60 pruebas aprobaron sin omisiones**;
Bandit, pip-audit, npm audit y Trivy no reportaron hallazgos en sus alcances
verificados. Esto no equivale a ausencia absoluta de riesgos ni a una prueba
OWASP exhaustiva.

La separación PostgreSQL **ya está aplicada a la instalación original**, tras
la autorización explícita del usuario. Antes se generó y restauró el respaldo
fresco `backups/20261030T160814369837892`; sus siete tablas coincidieron.
La API usa `medinet_runtime`, sin privilegios administrativos ni membresías.
Se rechazaron ocho operaciones prohibidas sobre la conexión efectiva de la API;
se comprobaron escritura transaccional revertida y consultas HTTP autenticadas.

API/web se actualizaron y los tres servicios están saludables. PostgreSQL no se
reinició ni recreó y conserva el volumen original. Las siete tablas conservan
todas sus filas/columnas; los roles y contraseñas preexistentes, `.env` y JWT
permanecen intactos. El archivo runtime nuevo es privado (0600) e ignorado.
El [plan](PLAN_POSTGRES_V05.md) está cumplido; queda pendiente la rotación
administrativa coordinada, HTTPS y las verificaciones remotas de Actions/AWS.

No se hizo commit, push, force push, reinicialización Git, cambios AWS,
modificación de `.env`, eliminación de registros originales ni de volúmenes.
Se agregó únicamente el rol técnico nuevo y se restringieron CREATE/TEMP de PUBLIC;
las cuentas preexistentes no se modificaron.

Documentación para continuar: [ENTREGA_TECNICA_V05.md](ENTREGA_TECNICA_V05.md).
Evidencia resumida: [JSON publicable](evidencias/auditoria-integral-v05.json).
Los documentos de revisiones anteriores se conservaron como históricos; sus
47 pruebas no se presentan como resultados de esta ejecución.

## 2. Problemas detectados y correcciones

| Problema | Corrección concreta | Verificación |
|---|---|---|
| Inicio de cirugías con horarios nominales distintos podía compartir paciente o profesional ya en otra operación iniciada | Consulta de recursos en `in_progress`, bajo los bloqueos comunes, antes de ocupar sala | Regresiones unitarias y dos inicios concurrentes por cada recurso en PostgreSQL |
| Intentos concurrentes de login podían sobrescribir el contador y eludir el bloqueo | Lectura y actualización de usuario con bloqueo de fila `FOR UPDATE` | Ocho intentos incorrectos simultáneos, luego contraseña correcta rechazada durante bloqueo |
| Nombres, especialidades y procedimientos con espacios pasaban la longitud mínima | Normalización antes de validar en esquemas Pydantic de creación | Regresiones de tres catálogos y suite funcional |
| Consulta de disponibilidad no tenía el mismo límite de equipo que la programación | `max_length=30` en lista de profesionales | Suite y esquema OpenAPI |
| Swagger detrás de Nginx no indicaba correctamente el prefijo de ejecución | `API_ROOT_PATH=/api`, manteniendo acceso directo local | Swagger en Chromium, servidor `/api` y readiness por esa ruta |
| Faltaban respuestas reales en documentación OpenAPI | 404 de disponibilidad/programación, 409 de pacientes/profesionales, 503 de readiness | Aserciones de OpenAPI dentro de la suite |
| API usaba administración y ejecutaba Alembic al arrancar | Runtime separado; mantenimiento con perfil explícito; CMD del servidor sin migraciones; grants mínimos | Migraciones reales, API funcional con runtime y ocho operaciones prohibidas rechazadas; aplicado también a la instalación original |
| Backend podía incluir parámetros privados en excepciones SQLAlchemy | `hide_parameters=True` | Configuración y revisión de errores |
| Login móvil conservaba dos columnas y aplastaba el panel informativo | Restaurar una columna bajo el breakpoint después de las reglas v0.5 | Inspección visual Chromium y aserción del grid |
| Encabezado móvil desbordaba horizontalmente | Reducir separaciones y retirar avatar redundante solo en pantallas pequeñas | Anchos de dashboard 320, 390 y 768 px sin desbordamiento |
| Pytest de desarrollo tenía un aviso en el catálogo de seguridad | 9.0.2 → 9.0.3; SCA extendido a desarrollo y navegador en CI | Reejecución de suite y pip-audit completo |
| Contexto Docker podía incluir dependencias frontend, informes y evidencias innecesarias | Exclusiones explícitas adicionales | Builds limpios y escaneo de imágenes |
| Publicación CI reconstruía imágenes después del gate de seguridad | Exportar imágenes escaneadas, checksum y artefacto; publicación sin reconstrucción | actionlint y roundtrip local save/load con IDs idénticos; ejecución remota pendiente |
| Entrega EC2 no separaba migración de ejecución | Respaldo restaurable previo, mantenimiento administrativo y reaplicación explícita de grants | Sintaxis y comandos operativos probados localmente, AWS pendiente |
| README dependía de un ZIP y comandos de administración dentro de API | Instalación desde GitHub, camino de actualización seguro y entrega técnica completa | Snapshot de archivos publicables, sin `.git` ni secretos, instalación desde cero |

Las actualizaciones previas de dependencias y Dockerfiles encontradas al iniciar
se conservaron y se volvieron a comprobar. No se atribuyen como correcciones
nuevas de esta sesión; su detalle se conserva en
[la revisión anterior](REVISION_FINAL_V05.md).

## 3. Pruebas y resultados

| Comprobación de esta sesión | Resultado y alcance |
|---|---|
| Suite completa final con PostgreSQL real | **60 passed; 0 failures; 0 errors; 0 skipped** |
| Login, JWT válido/inválido/expirado/malformado y roles | Aprobados |
| Catálogos, estados, horarios y referencias | Aprobados |
| Solapamientos por sala, paciente y profesional | Aprobados; consultas y escrituras |
| Tres tipos de reserva concurrente | Cada carrera devolvió 201 + 409; una sola reserva |
| Inicios compartiendo paciente o profesional | 200 + 409; se conserva una sola operación en curso |
| Transición simultánea de la misma cirugía | 200 + 409 |
| Ocho intentos fallidos concurrentes de login | Cuenta bloqueada; contraseña correcta devuelve 401 durante bloqueo |
| Alembic | Inicialización desde cero, baseline anterior, `0001 head` y `alembic check` aprobados |
| Grants runtime y permisos negativos | CRUD permitido funcional; DDL/DELETE/cambios de rol/hash/usuarios/Alembic rechazados con SQLSTATE 42501 |
| Seed | Repetible, concurrente, transaccional, sin duplicar ni reemplazar usuarios/datos existentes |
| Respaldo original | Dump y globals privados, SHA-256, listado y restauración real; siete tablas coinciden |
| Persistencia | Contenedor PostgreSQL de ensayo detenido/iniciado con el mismo volumen; fila ficticia conservada; volumen retenido |
| Preservación original | Comparación final de todas las columnas de las siete tablas y `.env`: sin cambios |
| Frontend | Build Vite aprobado; Docker multi-stage aprobado |
| Docker | Tres imágenes construidas; local/producción config válidas; Nginx válido |
| Copia limpia | Build de tres imágenes, migración, respaldo restaurado, provisioning, healthchecks, seed y alembic check aprobados |
| Roundtrip de imágenes CI | Exportación/carga de las tres imágenes conserva exactamente los IDs |
| Workflow | actionlint aprobado; ShellCheck de ambos scripts aprobado |
| Ejecución de GitHub Actions | **No verificada**; no se hicieron afirmaciones de éxito remoto |

Como comprobación adicional, se ejecutaron ocho regresiones nuevas contra una
copia del código original de HEAD: las ocho fallaron por los defectos descritos;
con el código corregido forman parte de las 60 pruebas aprobadas. No se alteró
el checkout original para ese contraste.

El único aviso Pytest es de deprecación del TestClient por HTTPX en Starlette.
No se silenció. La dependencia de pruebas puede migrarse en una tarea separada;
no afecta al runtime ni convierte la suite en fallida.

### Incidencias de ejecución, conservadas sin presentarlas como éxitos

- El TestClient en el sandbox inicial se bloqueó; se ejecutó fuera de ese
  sandbox. Posteriormente el usuario habilitó acceso completo.
- La primera suite completa produjo 45 aprobadas, dos fallos y trece errores
  porque Docker no publicó el puerto del clúster con red `internal`. Se corrigió
  la conexión **del ensayo** usando su IP interna. La suite final pasó completa.
- `pip-audit -r` en el host falló por falta de ensurepip. El mismo comando con
  Python 3.12 en contenedor y catálogo actualizado concluyó sin vulnerabilidades.
- Un Trivy web falló al compartir caché con otro proceso. Se repitió
  secuencialmente y se verificó el JSON. No se contaron archivos vacíos como éxitos.
- El primer ensayo de restauración detectó el servidor temporal de initdb.
  Se corrigió la espera usando TCP loopback, que solo habilita el servidor final.
  Otro ensayo detectó una referencia de imagen retirada tras reconstruir; el
  respaldo usa ahora la etiqueta del contenedor para restaurar. Ambos caminos
  fallaron antes de cualquier cambio de usuarios originales; la versión final
  restauró y comparó correctamente las siete tablas.
- Chromium no estaba instalado. Se descargó en almacenamiento privado de
  auditoría, sin instalar paquetes del sistema. Se corrigió un selector de
  pruebas antes de detectar/corregir los dos defectos móviles reales.
- La copia limpia necesitó incluir el perfil de mantenimiento al resolver su
  configuración de aislamiento; no fue un defecto del Compose entregado.
- Bandit marcó avisos genéricos en la primera propuesta de herramientas host
  Python/subprocess. Se sustituyeron esos nuevos borradores por scripts Bash
  explícitos, revisados con ShellCheck; no se añadieron supresiones Bandit ni CVE.

Las pruebas sobre PostgreSQL crean/eliminan exclusivamente estructuras de ensayo,
como ya hacía la suite previa. No apuntaron nunca a la base original. No se
eliminó ningún rol PostgreSQL ni volumen. Los usuarios originales se conservaron.

## 4. Escáneres y vulnerabilidades pendientes

| Control final | Resultado |
|---|---|
| Bandit 1.9.4, `app scripts` | 0 hallazgos |
| pip-audit 2.10.1, runtime | 0 vulnerabilidades conocidas |
| pip-audit 2.10.1, desarrollo y navegador | 0 vulnerabilidades conocidas; incluye runtime |
| npm audit, incluidas dependencias de desarrollo | 0 info/low/moderate/high/critical |
| Trivy 0.76.1, imagen API final | 0 vulnerabilidades y 0 secretos |
| Trivy 0.76.1, imagen web final | 0 vulnerabilidades y 0 secretos |
| Trivy 0.76.1, imagen PostgreSQL | 0 vulnerabilidades y 0 secretos |
| Trivy secretos sobre snapshot publicable | 0 secretos detectados |

Se incluyeron UNKNOWN/LOW/MEDIUM/HIGH/CRITICAL y avisos sin corrección. Los
resultados corresponden a las imágenes y catálogos registrados en la evidencia;
no garantizan que futuros catálogos o reconstrucciones sigan en cero.
No se ocultaron vulnerabilidades con allowlists, exclusiones o `ignore-unfixed`.

La ampliación SCA a herramientas de desarrollo detectó **PYSEC-2026-1845**
(alias GHSA-6w46-j5rx-g56g / CVE-2025-71176) en pytest 9.0.2. El catálogo devolvió
dos registros del mismo identificador: un hallazgo único, no dos vulnerabilidades
distintas. Se actualizó a 9.0.3, versión corregida indicada por el catálogo, y se
amplió el gate CI a `requirements-dev.txt` y `requirements-browser.txt`. La
resolución del navegador requiere glibc: el primer ensayo Alpine no pudo resolver
Playwright y se repitió en Python 3.12 Debian slim, sin omitir esa dependencia.

**Riesgos residuales reales:**

1. La credencial administrativa preexistente sigue siendo débil y debe rotarse
   de forma coordinada. Ya no está presente en el entorno de la API; esta usa una
   contraseña aleatoria distinta y un rol sin privilegios administrativos.
   La rotación exige actualizar su configuración privada y un canal alternativo;
   no se sobrescribió `.env`.
2. TLS, Security Groups y controles del host/runner todavía no se han verificado
   en AWS. No exponer esta demostración ni usar pacientes reales.
3. No existe un registro inmutable de auditoría de operaciones de negocio ni una
   política operativa de alertas completa. Los logs HTTP y contadores de login
   no cubren ese requisito por sí solos.
4. La exclusión de solapamientos depende del protocolo de bloqueos de la aplicación;
   no hay una restricción de exclusión de intervalos en la BD. No incorporar
   escritores que eludan ese protocolo; el rol runtime también debe custodiarse.
5. No se realizó DAST completo, prueba de penetración, validación externa de EC2
   ni comprobación remota exitosa de GitHub Actions.

## 5. Docker, PostgreSQL y datos

La instalación original mantiene tres contenedores independientes y saludables;
API/web ejecutan las correcciones nuevas. El contenedor DB no se recreó.
PostgreSQL solo está en la red interna y no publica 5432. API/web publican
127.0.0.1:8000/3000. Volumen original: `medinet-pab_postgres_data`, conservado.
Los procesos de las imágenes ensayadas usan UID 100 (API), 101 (web), 70 (motor
PostgreSQL). DB conserva entrypoint oficial que comienza con preparación de
permisos y baja al usuario postgres; no se afirma un `USER` fijo en esa imagen.
API/web tienen `cap_drop: ALL` y `no-new-privileges`.

Estado final de filas originales, comparadas por huellas de todas las columnas:

| Tabla | Filas conservadas |
|---|---:|
| operating_rooms | 8 |
| patients | 15 |
| medical_staff | 10 |
| surgeries | 13 |
| surgery_staff | 26 |
| app_users | 1 |
| alembic_version | 1, revisión 0001 |

El respaldo verificable original quedó privado en
`backups/20261030T151525496022Z`; el procedimiento final Bash también se ejecutó
con éxito en `backups/20261030T153534367802186`. Ambos están ignorados por Git y
Docker. No incorporar dumps, roles globales ni huellas privadas a la entrega.

La composición activa separa el rol nuevo runtime del propietario existente,
con contraseña aleatoria SCRAM y permisos explícitos. En la copia se probó login,
lectura, creación de catálogos, programación, conflictos e inicio/finalización
con ese rol. En el entorno original se verificaron además privilegios, consultas
autenticadas, escritura revertida y ocho denegaciones. No se le concedieron DDL,
DELETE ni modificación de usuarios/roles.
Mantenimiento sigue usando administración y solo existe durante su tarea.

Las copias con tmpfs, contenedores de restauración y el volumen de persistencia
pertenecen al ensayo. Al cerrar se detienen sus servicios; no se ejecuta down -v
ni se elimina ningún volumen. Los comandos de la entrega distinguen operación
normal de preparación inicial y de recuperación.

## 6. Frontend y backend en navegador

Se usó Chromium con las imágenes construidas y una copia restaurada de PostgreSQL,
usuarios ficticios nuevos de prueba y la conexión runtime restringida. No se
probaron contraseñas ni se escribieron cirugías en la instalación original. Tras
activar runtime se comprobaron consultas reales con un JWT técnico efímero, sin
mostrarlo ni conservarlo; no se atribuye a ese chequeo un login con contraseña.

Verificado: login de admin, coordinator y viewer; ocho tarjetas; programación y
consulta desde React; inicio y finalización; sala en sanitización; un 409 con
mensaje claro al intentar liberar una sala en curso; controles ocultos/desactivados
de viewer; coordinator sin creación de catálogos; salida de sesión; Swagger y
rutas del proxy; diseño a 320/390/768 y escritorio de 1440 px.

**Cero errores JavaScript.** Chromium registró exactamente un error de recurso
HTTP 409, provocado deliberadamente por la prueba del mensaje de conflicto.
No se reporta falsamente consola vacía durante esa prueba negativa. Los flujos
normales no emitieron errores de consola.

Evidencia: [escritorio](evidencias/auditoria-integral-dashboard.png),
[login móvil](evidencias/auditoria-integral-login-mobile.png),
[dashboard móvil](evidencias/auditoria-integral-dashboard-mobile.png),
[Swagger](evidencias/auditoria-integral-swagger.png).

## 7. GitHub y revisión de archivos

Rama `main` con upstream local `origin/main`, remoto `origin` conservado en el repositorio esperado; historial
existente sin reescritura. La consulta remota HEAD no fue accesible con las
credenciales disponibles; no se infiere el estado de ejecuciones Actions.
Las referencias públicas upload/download-artifact usadas para fijar SHA sí
se comprobaron contra sus etiquetas v4.

`.env`, `.env.runtime`, respaldos, claves, caches y artefactos temporales están
ignorados. Las dos rutas de entorno no aparecen versionadas ni en su historial.
La plantilla contiene únicamente nombres ficticios y secretos vacíos. No se
copiaron secretos ni `.git` a la construcción limpia.

La comparación privada por subcadenas encontró la contraseña administrativa débil
como parte de un literal genérico de validación de caracteres en código e
historial. No es una asignación de credencial incrustada ni justifica eliminar
ese validador o reescribir Git. Refuerza la necesidad de rotar la contraseña;
no se publicó su valor. JWT no apareció en fuentes/historial. Trivy de secretos
sobre los archivos publicables quedó en cero. Configuración/historial de imágenes
y logs revisados no contienen las credenciales activas.

La revisión incluyó los cambios previos y los nuevos. Archivos del conjunto final:

- Backend: [db.py](../app/db.py), [main.py](../app/main.py),
  [schemas.py](../app/schemas.py), [security.py](../app/security.py),
  [requirements.txt](../requirements.txt), [requirements-dev.txt](../requirements-dev.txt).
- Docker/configuración: [Dockerfile](../Dockerfile),
  [Dockerfile.postgres](../Dockerfile.postgres),
  [frontend/Dockerfile](../frontend/Dockerfile),
  [compose.yaml](../compose.yaml), [compose.prod.yaml](../compose.prod.yaml),
  [.dockerignore](../.dockerignore), [.env.example](../.env.example).
- Frontend: [styles.css](../frontend/src/styles.css); sin cambios decorativos
  ni nuevos componentes de producto.
- Operación: [backup.sh](../scripts/backup.sh),
  [provision_runtime.sh](../scripts/provision_runtime.sh),
  [db_privileges.py](../scripts/db_privileges.py),
  [create_user.py](../scripts/create_user.py).
- CI: [ci-cd.yml](../.github/workflows/ci-cd.yml).
- Pruebas: [test_auth.py](../tests/test_auth.py),
  [test_v05.py](../tests/test_v05.py),
  [test_concurrency.py](../tests/test_concurrency.py),
  [test_privileges.py](../tests/test_privileges.py),
  [browser_smoke.py](../tests/browser_smoke.py),
  [requirements-browser.txt](../requirements-browser.txt).
- Documentación: [README](../README.md),
  [plan PostgreSQL](PLAN_POSTGRES_V05.md),
  [entrega para Matías](ENTREGA_TECNICA_V05.md), este informe,
  [revisión final anterior](REVISION_FINAL_V05.md),
  [resultados de seguridad anteriores](SEGURIDAD_V05_RESULTADOS.md),
  evidencia histórica encontrada al iniciar y nueva evidencia integral.

El workflow define Build, Test, Security Scan y Deployment. Publicación requiere
push a main y gates previos; usa exactamente las imágenes escaneadas. Deployment
requiere `ENABLE_EC2_DEPLOY=true`, environment `production`, runner EC2 privado y
configuración privada ya preparada. Se validó localmente; **no se probó remoto**.

## 8. Pasos pendientes de Matías y decisión commit/push

1. Separación PostgreSQL aplicada y verificada: conservar `.env.runtime`, usar
   administración únicamente para mantenimiento y repetir los controles si cambia
   el esquema o la política de privilegios. No volver a conectar la API como superusuario.
2. Rotar la contraseña administrativa de forma coordinada, con acceso alternativo,
   custodia y actualización privada. No cambiar solo una variable de Compose.
3. El código y la activación local están comprobados y **listos para revisión y
   commit/push autorizado**. No se realizó ninguno. Esto no certifica seguridad
   absoluta ni reemplaza la rotación administrativa y la preparación AWS/HTTPS.
4. Dar acceso al repositorio a Matías y comprobar la primera ejecución real de
   Actions, permisos GHCR, artefactos y correspondencia de SHA publicado/desplegado.
5. Preparar EC2 Academy, runner, HTTPS, SG mínimos, dominio, respaldos externos,
   límites de recursos y monitorización. No activar deployment antes de eso.
6. Verificar el despliegue desde otro equipo y completar el informe académico
   con evidencia real y riesgos residuales; aplicar el marco ISO/OWASP de la
   entrega técnica sin afirmar certificación ni pruebas no realizadas.

El cambio PostgreSQL autorizado está completado. No se requiere otra aprobación
para esta activación. Las siguientes decisiones son la rotación administrativa
coordinada y, cuando el usuario lo solicite, commit/push y preparación remota.

## 9. Activación autorizada sobre la instalación original

Respaldo previo fresco: `backups/20261030T160814369837892`, dump/globals con SHA-256,
restauración real y comparación de las siete tablas. Se detuvieron brevemente
API/web para evitar escrituras durante el respaldo; DB permaneció activa.

Se ejecutó Alembic con mantenimiento (`0001 head`, sin diferencias), se creó el
rol con SCRAM y se activaron API/web con las imágenes comprobadas. Mantenimiento
y provisioning usan `--no-deps` en esta operación para no recrear DB al cambiar
una etiqueta de imagen. Se verificaron las ocho denegaciones, ausencia de flags
administrativos/membresías, contraseña runtime distinta y fuerte, consultas
autenticadas 200, rechazo 401 sin token, Swagger/readiness y ausencia de secretos
activos en logs. La prueba de escritura se revirtió íntegramente, sin nuevas filas.

El propietario y los hashes de sus contraseñas coinciden con el respaldo; `.env`
y JWT están idénticos. Los 8 pabellones, 15 pacientes, 10 profesionales, 13 cirugías,
26 relaciones y el usuario original siguen intactos. El contenedor y el volumen
DB son los mismos. La contraseña administrativa no se rotó: permanece como
pendiente independiente y ya no se entrega a la API.
