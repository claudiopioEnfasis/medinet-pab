# MediNet PAB v0.5 — Revisión final de seguridad y CI/CD

> Documento de una revisión anterior. Para el estado de esta entrega, consultar
> [AUDITORIA_INTEGRAL_V05.md](AUDITORIA_INTEGRAL_V05.md) y
> [ENTREGA_TECNICA_V05.md](ENTREGA_TECNICA_V05.md). Los resultados históricos no
> acreditan la aplicación de los cambios nuevos a la instalación original.


Fecha: **30 de octubre de 2026**, America/Santiago.

## Resultado

La instalación local conserva **API 0.5.0**, su diseño React y los registros
originales. Las tres imágenes reconstruidas tienen **cero hallazgos Trivy en
todas las severidades consultadas**. Bandit, pip-audit y npm audit aprobaron.
La suite final ejecutó **47 pruebas: 47 aprobadas, ninguna omitida**.

Esto permite continuar la preparación de v1.0, pero no equivale a autorizar una
exposición pública: quedan pendientes el rol PostgreSQL de la aplicación, la
fortaleza de su contraseña y los controles operativos de AWS/HTTPS. No se hizo
push ni se desplegó en AWS.

## 1. Vulnerabilidades detectadas y corregidas

Se repitieron los escaneos anteriores antes de actualizar. Trivy se ejecutó
también sobre PostgreSQL y sin `ignore-unfixed`, abarcando todos los niveles.

| Control | Antes | Después |
|---|---:|---:|
| Bandit, app y scripts | 0 | 0 |
| pip-audit, inventario de imagen API | 37 entradas en 3 paquetes | 0 |
| npm audit de producción | 0 | 0 |
| npm audit completo, incluido desarrollo | No medido inicialmente en esta revisión | 0 |
| Trivy API | 26: 1 CRITICAL, 8 HIGH, 15 MEDIUM, 2 LOW | 0 |
| Trivy web | 229: 1 CRITICAL, 46 HIGH, 82 MEDIUM, 96 LOW, 4 UNKNOWN | 0 |
| Trivy PostgreSQL | 61: 1 CRITICAL, 25 HIGH, 31 MEDIUM, 3 LOW, 1 UNKNOWN | 0 |

Son entradas de hallazgo por paquete/componente, no necesariamente CVE únicas.
Los 37 avisos Python contienen duplicados: corresponden a 26 combinaciones
únicas de paquete e ID. Sus aliases CVE/GHSA se conservaron en la evidencia.

Ejemplos CRITICAL identificados por el catálogo:

| ID | Componente anterior | Corrección aplicada |
|---|---|---|
| CVE-2026-102268 | PyJWT 2.13.0 en API | PyJWT 2.15.1 |
| CVE-2026-111497 | brotli-libs en imagen web anterior | Nueva base Nginx slim y paquetes corregidos; la dependencia vulnerable no permanece |
| CVE-2025-68121 | Biblioteca Go 1.24.6 del binario gosu de PostgreSQL | Recompilación con Go 1.27.3 |

También se corrigieron los avisos de Starlette, pip, bibliotecas Alpine de la
imagen web y la biblioteca estándar Go. Durante la recompilación de gosu se
identificaron dos avisos adicionales y se corrigieron:

- **CVE-2026-61801**, MEDIUM: `github.com/moby/sys/user` 0.1.0 → 0.4.1.
- **CVE-2026-39824**, UNKNOWN según el proveedor: `golang.org/x/sys` 0.1.0 → 0.44.0.

El [anexo CVE/GHSA](evidencias/revision-final-vulnerabilidades.md) enumera los
HIGH/CRITICAL y los avisos Python con dependencia, versión, severidad y fuente.
El [JSON completo](evidencias/revision-final-seguridad.json) conserva también
LOW/MEDIUM/UNKNOWN, digests de imágenes y resultados posteriores.

**No se añadieron allowlists, filtros de paquetes ni exclusiones de CVE.** Se
retiró del pipeline la omisión de avisos sin corrección y npm ahora revisa
también las dependencias de desarrollo. Los tres gates Trivy HIGH/CRITICAL,
sin omitir avisos sin corrección, terminaron con código **0**.

## 2. Dependencias e imágenes actualizadas

| Componente | Antes | Después |
|---|---|---|
| FastAPI | 0.128.2 | 0.162.0 |
| Starlette | 0.50.0 transitiva | 1.10.0 fijada explícitamente |
| PyJWT | 2.13.0 | 2.15.1 |
| psycopg | Rango `>=3.2,<4` | 3.3.6, misma versión efectiva, fijada |
| pip del builder API | 25.0.1 | 26.2.2 |
| pip del runtime API | Instalado | Retirado después de instalar los wheels: no es necesario para ejecutar la aplicación |
| Python del runtime | Rama 3.12 Alpine | 3.12.16, base actual fijada por digest |
| Nginx | Rama 1.29 Alpine | 1.30.6, base `1.30-alpine-slim` fijada por digest |
| Motor PostgreSQL | 17.11 | **17.11 conservado** |
| gosu de PostgreSQL | 1.19, Go 1.24.6 | 1.19, Go 1.27.3 y dependencias corregidas |

La actualización conjunta FastAPI/Starlette se comprobó con la resolución de
dependencias y las pruebas, sin forzar Starlette fuera de los requisitos
de FastAPI. Referencias primarias: [FastAPI](https://fastapi.tiangolo.com/release-notes/),
[Starlette](https://starlette.dev/release-notes/) y
[PyJWT](https://pyjwt.readthedocs.io/en/stable/changelog.html).

`Dockerfile.postgres` conserva la base oficial y su entrypoint. Compila el
mismo código de gosu 1.19, fijado al commit
`6456aaa0f3c854d199d0f037f068eb97515b7513`, con Go corregido y las dos
dependencias transitivas actualizadas. El SDK Go permanece solo en el builder.
Se verificaron `gosu --version`, el cambio al usuario postgres, la inicialización
de una base nueva, la restauración y el uso del volumen existente.

API y frontend siguen usando multi-stage y Alpine. Se aplican actualizaciones
Alpine durante la construcción. La imagen slim y la retirada del instalador pip
reducen componentes innecesarios del runtime; no eliminan funciones de negocio.
Los archivos React/JSX/CSS y su lockfile no se modificaron en esta revisión.

### Docker en ejecución

- API, web y PostgreSQL siguen separados.
- Procesos PID 1 verificados sin root: API UID **100**, web **101**, DB **70**.
  PostgreSQL conserva el entrypoint oficial que prepara permisos y baja de UID
  mediante gosu antes de ejecutar el motor.
- API/web conservan `cap_drop: ALL` y `no-new-privileges`.
- DB permanece exclusivamente en la red interna, sin puerto publicado.
- API/web se publican solo en loopback; producción continúa preparada para un
  proxy HTTPS y no expone directamente la API.
- Mismo proyecto, redes y volumen `medinet-pab_postgres_data`.
- Tres healthchecks saludables, cero reinicios y sin errores relevantes en logs.
- No se encontraron las credenciales activas en la configuración ni en el
  historial de construcción de las imágenes. `.env` sigue fuera de Git.

## 3. Respaldo, migraciones y persistencia

Antes de actualizar la instalación se creó un respaldo privado en:

```text
/home/midnight/respaldos-medinet/final-v05-20261030T045918/
```

Incluye `database.dump`, `globals.sql`, `SHA256SUMS`, inventario y diagnósticos
privados. La carpeta tiene permisos `0700` y los respaldos `0600`.
**No deben incorporarse a Git ni compartirse**, pues contienen registros y
hashes de contraseñas.

Se detuvieron API/web para obtener un estado estable, se verificó
`pg_restore --list` y se restauró el archivo realmente en PostgreSQL corregido,
con almacenamiento tmpfs independiente del volumen original. Se compararon
conteos y huellas de todas las filas de las seis tablas; coincidieron.

Primero se ensayaron `scripts.migrate`, `alembic check` y `alembic current` sobre
esa copia. Después se recreó PostgreSQL con su imagen corregida y el mismo
volumen; se ejecutó la migración en un contenedor de una sola ejecución antes
de levantar API/web. Todas las operaciones pasaron.

El esquema ya estaba en **0001 (head)** y no necesitó una migración nueva.
`alembic check` no detectó diferencias. La comparación final confirmó todos los
valores originales, incluidos usuario, rol, estado y hash de contraseña.
`.env` se conservó byte por byte, con permisos `0600`. No se ejecutó `down -v`
ni ninguna eliminación de volúmenes.

| Datos originales conservados | Cantidad final |
|---|---:|
| Pabellones | 8 |
| Pacientes ficticios | 15 |
| Profesionales | 10 |
| Cirugías | 13 |
| Relaciones cirugía/equipo | 26 |
| Usuarios de aplicación | 1 |

## 4. Resultados funcionales

| Comprobación | Resultado |
|---|---|
| Suite completa con PostgreSQL real de pruebas | **47 aprobadas, ninguna omitida** |
| Dos reservas concurrentes | Una 201 y otra 409 |
| Seed repetible y dos cargas simultáneas | Aprobados |
| Reversión del seed ante fallo y conservación de registros | Aprobadas |
| JWT con exp/nbf/iat malformados | 401, sin errores 500 |
| JWT sin sub/iss/iat/exp obligatorios | 401 |
| Autenticación y permisos anteriores | Aprobados |
| Login real de administrador de prueba en copia PostgreSQL | 200 |
| Viewer de prueba consulta pero no modifica | 200 / 403, sin inserción |
| Dashboard con ocho pabellones y cuatro estados | Correcto |
| Programación y consulta desde React | 201 y agenda visible |
| Conflictos individuales de sala, paciente y equipo | Tres rechazos 409 |
| Entradas de horario sin zona horaria | 422 |
| Inicio/finalización y cambio de estado desde React | Correctos |
| React, cierre de sesión y JavaScript de página | Correctos, cero errores de página |
| Swagger renderizado en navegador | Correcto |
| `/health/ready` directo y mediante Nginx | 200 |
| OpenAPI de la instalación | Versión de aplicación 0.5.0 |
| Nginx, Compose local/producción y Alembic | Correctos |
| Datos y usuarios después de actualizar | Íntegramente conservados |

Las operaciones de escritura del navegador y el login con contraseña se
realizaron sobre una **copia restaurada**, con administrador y viewer ficticios
creados solo allí. La copia usó las mismas imágenes corregidas. En la instalación
original se verificó el dashboard mediante una sesión técnica temporal de solo
lectura y se comprobó Swagger/readiness. No se probaron ni cambiaron las
contraseñas originales, conforme a la preferencia previa de comprobación manual.

Las 47 pruebas incluyen siete nuevas regresiones de JWT. Emitieron un aviso de
deprecación del TestClient: Starlette recomienda `httpx2` en lugar del `httpx`
actual de pruebas. No se suprimió el aviso; no impidió las pruebas y no afecta
al runtime de producción.

Evidencia: [resultados JSON](evidencias/revision-final-pruebas.json),
[dashboard de la instalación](evidencias/revision-final-produccion.png),
[dashboard en copia de pruebas](evidencias/revision-final-dashboard.png) y
[Swagger](evidencias/revision-final-swagger.png).

## 5. Seguridad residual y límites

### Catálogos de vulnerabilidades

No quedan avisos CVE/GHSA de dependencias o imágenes en los escaneos finales,
incluidos los niveles sin corrección disponible. Este resultado corresponde
a las versiones, catálogos y fecha registrados; el pipeline conserva los gates.

Se ejecutó pip-audit sobre las fuentes resueltas, el inventario real de la
imagen y el comando completo `pip-audit -r requirements.txt` en Python 3.12
aislado: todos aprobaron. El contenedor permitió reproducir el comando del CI
sin depender del `ensurepip` ausente en el Python del host Mint.

### Configuración que debe resolverse antes de AWS

1. **El rol PostgreSQL usado por la aplicación es superusuario**, con capacidad
   de crear roles y bases. Antes de exponer el servicio corresponde separar el
   rol de migración/administración del rol de ejecución, con permisos mínimos.
2. **La contraseña PostgreSQL no supera una comprobación básica local de
   longitud/diversidad.** No se imprime ni se cambia aquí. Hace falta planificar
   una rotación coordinada entre PostgreSQL y la configuración privada; editar
   solo `POSTGRES_PASSWORD` no cambia la contraseña almacenada en una base existente.

Estos pendientes no se ocultaron. Corregirlos ahora requeriría cambiar roles,
credenciales y `.env`, contrario a las restricciones de esta tarea. La
conservación de contraseñas de usuarios de la aplicación es independiente de
la futura rotación del rol técnico de PostgreSQL.

La instalación permanece local y de demostración. HTTPS, controles operativos
AWS y evidencia de disponibilidad externa aún no están implementados.

## 6. GitHub Actions y Git

Repositorio local existente comprobado: rama **main**, `origin` en
`https://github.com/claudiopioEnfasis/medinet-pab.git`. HEAD conservado:
`a1d0b4ca08360b9acafda87eb860e61b3fe023a1`. No se inicializó otro repositorio,
no se reescribió historial, no se hizo commit ni push en esta revisión.

| Requisito CI/CD | Preparación verificada |
|---|---|
| Build | Construye API, frontend y PostgreSQL corregido |
| Test | Suite, concurrencia PostgreSQL, Alembic y seed idempotente |
| Security Scan | Bandit, pip-audit, npm completo y Trivy de tres imágenes |
| Publicación | Tres imágenes GHCR por SHA, solo main y después de los controles |
| Deployment | EC2 self-hosted, environment production, condicionado a ENABLE_EC2_DEPLOY=true |

La integración utiliza ahora PostgreSQL construido desde `Dockerfile.postgres`,
con tmpfs y puerto loopback, por lo que prueba la misma variante que se publica.
`actionlint` aprobó sintaxis, expresiones, dependencias de jobs y scripts.
También se ejecuta como paso del CI.

Las acciones se fijaron por SHA de sus etiquetas verificadas. Trivy se fija
en **0.76.1**, coincidiendo con el escáner local; Bandit en 1.9.4 y pip-audit
en 2.10.1. Se escanean los avisos sin corrección y también las dependencias npm
de desarrollo. La entrega publica `-api`, `-web` y `-db` con la misma etiqueta.

El workflow usa `secrets.GITHUB_TOKEN` para GHCR y no contiene claves ni tokens
temporales AWS. Los datos explícitos de PostgreSQL/JWT del job de pruebas son
exclusivamente desechables. Producción conserva su `.env` privado. El login
Docker del runner EC2 usa un `DOCKER_CONFIG` temporal y lo elimina al salir.
El despliegue valida Compose y espera servicios saludables antes del chequeo HTTP.

**Resultados remotos:** la conexión GitHub y la consulta API devolvieron 404
para Actions con la autorización disponible. No se pudieron leer ejecuciones,
jobs ni logs remotos; no se atribuyen fallos o éxitos que no se observaron.
Esto no afecta al repositorio local existente, pero las comprobaciones locales
no acreditan una ejecución real de GitHub Actions. Los cambios siguen sin publicar.

## 7. Rúbrica: cumplido y pendiente

| Criterio | Estado |
|---|---|
| Backend REST, Swagger/OpenAPI | Verificado localmente |
| Relacional, FK/unique/CHECK y migraciones | Conservado; esquema y regresión aprobados |
| Entradas, JWT/RBAC y disponibilidad triple | Pruebas y flujos reales aprobados |
| Mitigaciones de acceso e inyección | Pruebas de roles, tokens e inputs aprobadas; no equivalen a una auditoría OWASP exhaustiva |
| Docker separado, datos persistentes y red privada | Verificado, procesos sin root y healthchecks correctos |
| Build/Test/Security Scan | Implementados y comprobados localmente |
| Continuous Deployment | Preparado, no ejecutado en EC2 |
| Pipeline exitoso en GitHub | Pendiente de acceso/evidencia real |
| Mínimo privilegio PostgreSQL y fortaleza de credencial técnica | Pendientes antes de exposición pública |
| HTTPS, AWS operativo, disponibilidad externa | Pendientes para v1.0 |
| Informe ISO 27034 y evidencia final de evaluación | Pendientes; estos controles no constituyen certificación |

## 8. Archivos modificados

- `requirements.txt`: versiones compatibles corregidas y driver fijado.
- `Dockerfile`: base fijada, pip builder corregido y runtime reducido.
- `frontend/Dockerfile`: Nginx slim corregido y UID final explícito.
- `Dockerfile.postgres`: nueva construcción de PostgreSQL con gosu corregido.
- `compose.yaml`, `compose.prod.yaml`: imagen DB local/publicada correspondiente.
- `.github/workflows/ci-cd.yml`: DB de pruebas/construcción/escaneo/publicación,
  acciones fijadas, gates completos y credencial Docker temporal.
- `tests/test_auth.py`: siete casos nuevos de regresión JWT.
- `.env.example`: documenta también el sufijo de imagen `-db`; `.env` intacto.
- `README.md`: arquitectura y referencias de seguridad actualizadas.
- `docs/SEGURIDAD_V05_RESULTADOS.md`: enlace que preserva el carácter histórico
  de la auditoría anterior.
- `docs/REVISION_FINAL_V05.md`: este informe.
- `docs/evidencias/revision-final-seguridad.json` y
  `revision-final-vulnerabilidades.md`: comparación de vulnerabilidades.
- `docs/evidencias/revision-final-pruebas.json`: evidencia funcional y límites.
- `docs/evidencias/revision-final-dashboard.png`, `revision-final-produccion.png`
  y `revision-final-swagger.png`: capturas sin contraseñas ni tokens.

## 9. Pasos concretos para AWS Academy / v1.0

1. Resolver de forma autorizada el rol técnico PostgreSQL y su contraseña,
   preservando los usuarios de la aplicación. Probar otra vez migración, login
   y disponibilidad tras esa separación.
2. Revisar estos cambios y ejecutar Actions en el repositorio con autorización;
   obtener evidencia de Build/Test/Security Scan y de las tres imágenes por SHA.
3. Preparar la EC2 del Learner Lab y un runner confiable compatible con las
   acciones fijadas. Usar la arquitectura de imágenes probada (AMD64) o validar
   explícitamente otra. No introducir credenciales AWS temporales en el workflow.
4. Configurar dominio/TLS y proxy HTTPS, accesos mínimos y DB privada. La
   composición actual en loopback requiere ese proxy antes de acceso externo.
5. Automatizar respaldos privados fuera de la instancia, ensayar restauración
   y definir retorno a una imagen anterior y tratamiento de migraciones fallidas.
6. Activar la entrega EC2 solo después de esas verificaciones, comprobar desde
   un equipo externo y completar la evidencia de la rúbrica e informe ISO 27034.
