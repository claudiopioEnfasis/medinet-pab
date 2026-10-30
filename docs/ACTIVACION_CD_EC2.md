# Activación controlada de CD en la EC2 existente

Preparado localmente, 30-10-2026. **No habilitado, sin push y sin ejecutar cambios
en AWS.** El propietario informa aplicación, usuarios/datos y HTTPS operativos en
https://medinet-pab.duckdns.org. Ese estado no se verificó remotamente en esta tarea.

## Comportamiento implementado

[Workflow](../.github/workflows/deploy-ec2.yml) separado de CI: workflow_run del CI
exitoso de push main, o dispatch manual desde main con SHA completo. Además exige
SHA actual de main y job «Publicar imágenes versionadas en GHCR» exitoso de ese
mismo run. En CI, publicación depende de tests, builds y todos los escáneres.
No entrega PR ni código de forks. Runner efímero de GitHub, sin runner en EC2 ni
claves AWS. contents/actions/package tienen solo los permisos necesarios por job.

**Ambas variables ENABLE_EC2_DEPLOY y EC2_SECURITY_REVIEWED deben estar true para
que empiece CD**. No se crearon ni modificaron aquí. El Environment production
requiere protección efectiva; el YAML no configura revisores por sí solo.

El [script](../deploy/deploy.sh) exige archivos privados 0600, estado de release
válido y coincidencia de las imágenes DB/API/web con las ejecutadas. Si falta ese
estado, falla sin bootstrap ni recrear datos. Lee compose.prod.yaml y llama
scripts/backup.sh; no requiere directorio bin. El dispatcher llama deploy/deploy.sh.

Secuencia: readiness loopback → descargar solo API/web/maintenance → exigir mismo
head Alembic que esquema vigente → detener API/web → backup de datos y roles,
checksum, restauración aislada en tmpfs sin red y comparación de siete tablas →
mantenimiento/migración → grants → levantar API/web con --no-deps y esperar salud →
readiness y misma identidad del contenedor DB → actualizar estado de release.
El workflow también comprueba HTTPS /api/health/ready antes y después del SSH.

No se hace pull/up/recreate del servicio db, no se cambia su tag, no se ejecuta
seed, creación de usuarios ni --create de roles; no se cambia contraseña/JWT.
Se reaplican grants existentes después de backup, sin rotación. No se edita .env,
.env.runtime, Nginx, certificados, dominio ni reglas AWS. Habrá una breve ventana
sin API/web mientras el backup se verifica; planificarla con el compañero.

## 1. Revisar la instalación antes de activar (por el administrador)

Estos pasos son instrucciones futuras, **no ejecutadas por el agente**.

- Confirmar la raíz real. El dispatcher usa /opt/medinet-pab. Si el checkout actual
  está en otra ruta, ajustar la constante root del dispatcher de forma revisada
  antes de instalarlo. No mover una instalación activa por seguir esta guía.
- Conservar el proyecto Compose y volumen actuales. Revisar nombre de proyecto,
  contenedor db y montaje persistente con docker inspect, mostrando únicamente
  esos campos; nunca volcar todo Config.Env ni docker compose config en logs.
- Mantener compose.prod.yaml, deploy/deploy.sh, deploy/dispatch.sh y scripts/backup.sh
  con esas rutas. Instalar estos scripts revisados mediante cuenta administrativa;
  no hacer git reset/clean, no reemplazar la composición personalizada del servidor
  sin comparar diferencias, y no sobrescribir configuración privada o TLS.
- La cuenta dedicada de entrega debe leer los archivos privados existentes y
  usar Docker, escribir .deployment y backups, pero no modificar scripts,
  composición ni directorios padre. Docker equivale a privilegios root: requiere
  revisión administrativa explícita, código confiable y PR aprobados en main.
- Verificar Docker/Compose moderno, Bash, curl, Python3, flock, gzip, coreutils,
  espacio y RAM para restaurar el dump en tmpfs; el backup puede tardar. Ajustar
  timeout del job con evidencia si 30 minutos no bastan, no quitar verificación.
- Confirmar que el rol medinet_runtime existe con los grants definidos por el
  proyecto. El paso db_privileges falla de forma segura si falta o es privilegiado.
  Resolver incompatibilidades manualmente con respaldo; no volver a provisionar
  usuarios/seed en una instalación existente.

## 2. Registrar el release realmente activo

Crear .deployment (0700) y current.env (0600) **solo si no existen**; si ya existen,
comparar su contenido no secreto con la instalación y detenerse ante diferencias.
Deben contener exactamente estas tres claves, con tags SHA reales:

```text
IMAGE_PREFIX=ghcr.io/claudiopioenfasis/medinet-pab
IMAGE_TAG=sha-<40 hex del release API/web activo>
POSTGRES_IMAGE_TAG=sha-<40 hex de la imagen DB activa>
```

Los marcadores no son valores válidos para ejecutar. Obtener cada imagen con
inspect --format '{{.Config.Image}}' del contenedor correspondiente, sin imprimir
variables. API/web deben compartir release y coincidir con current.env. No elegir
main arbitrariamente ni cambiar DBtag para igualarlo a API/web. Si las imágenes
activas se identifican por digest en vez de tag o pertenecen a prefijos distintos,
este script rechaza la instalación: requiere adaptación revisada antes de activar.
Los archivos .env y .env.runtime deben seguir con sus contenidos y permisos 0600.
No cambiar de nombre el volumen ni cambiar el proyecto Compose.

## 3. Clave SSH exclusiva y comando forzado

En una estación administrativa confiable, generar una clave nueva dedicada
exclusivamente a CD (no reutilizar la de acceso personal):

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/medinet-pab-deploy -N '' -C medinet-pab-cd
```

La clave sin passphrase permite el cliente no interactivo del workflow; guardarla
únicamente como Secret protegido, con acceso administrativo mínimo. No generarla
en el repositorio, enviarla por chat, imprimirla en logs ni versionarla.

Agregar la pública a authorized_keys de la cuenta dedicada con una única línea:

```text
restrict,command="/opt/medinet-pab/deploy/dispatch.sh" ssh-ed25519 <publica> medinet-pab-cd
```

Verificar OpenSSH compatible con restrict y permisos de .ssh 0700/authorized_keys
0600. No permitir PTY, forwarding ni comandos arbitrarios para esa clave. El
comando forzado admite solamente `deploy <SHA de 40 hex>`; ejecuta el script
protegido existente, no copia scripts enviados por SSH. No hacer pruebas del
comando deploy contra producción sin autorización de despliegue.

Obtener y verificar huella/known_hosts mediante una sesión administrativa confiable
(por ejemplo contrastar la huella con la consola de la instancia). No confiar
ciegamente en ssh-keyscan ni desactivar StrictHostKeyChecking. Para puerto no
estándar, known_hosts debe contener [host]:puerto. Una IP/DNS nueva tras reiniciar
Academy puede exigir actualizar el secret, después de verificar identidad.

## 4. GitHub Environment y Secrets

Crear production con revisores requeridos, impedir autoaprobación, restringir a
main y limitar bypass. Comprobar disponibilidad real según plan/visibilidad. Si no
pueden imponerse las protecciones requeridas, mantener CD deshabilitado.
Proteger main mediante PR/revisión y checks obligatorios, especialmente cambios
sobre workflows y scripts. No dar Secrets o permisos de escritura a PR de forks.

Secrets del Environment production (no variables públicas):

| Nombre | Contenido requerido |
|---|---|
| EC2_HOST | DNS/IP SSH actual, sin esquema ni ruta |
| EC2_USER | Cuenta dedicada con comando forzado |
| EC2_SSH_PRIVATE_KEY | Clave privada exclusiva completa; no mostrar su valor |
| EC2_KNOWN_HOSTS | Línea(s) de identidad del host ya contrastadas |

Variable EC2_PORT: puerto SSH, por defecto 22. GITHUB_TOKEN lo genera Actions con
packages:read en entrega, sin PAT persistente. Confirmar acceso del repositorio a
los paquetes privados API/web de GHCR. El token viaja por stdin sobre SSH y Docker
usa un directorio de autenticación temporal que el dispatcher limpia al terminar.
No se escribe en .env ni .env.runtime. No se necesita AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY ni AWS_SESSION_TOKEN.

No abrir SSH globalmente para hacer funcionar runners de GitHub, cuyas IP son
dinámicas. Preparar salida controlada/red administrativa o una estrategia de
conectividad revisada, manteniendo SG mínimos. Eso requiere trabajo separado del
administrador; este cambio no modifica SG ni instala runners.

## 5. Ensayo y activación futura

1. Revisar cambios locales y autorizar commit/push por separado. Comprobar CI y
   publicación GHCR exitosos del SHA exacto. CD debe seguir omitido con ambas
   variables false/ausentes, incluso si se ejecuta dispatch manual.
2. Preparar acceso, estado de release y capacidad de backup. Ensayar primero en
   una instalación de pruebas independiente, con copia ficticia y el mismo Compose
   de producción: backup restaurable, fallo de migración/grants, fallo readiness y
   recuperación. Los mocks locales no sustituyen ese ensayo.
3. Tras autorización explícita de entrega, configurar ENABLE_EC2_DEPLOY=true y
   EC2_SECURITY_REVIEWED=true como variables del repositorio. Preferir primera
   entrega manual desde main con image_sha igual al main actual y CI publicado.
   Aprobar el Environment con la persona designada. No ejecutar estos pasos ahora.
4. Después, pushes aprobados a main con CI completo exitoso podrán pedir aprobación
   production y entregar ese SHA. Concurrencia serializada y sin cancelación
   automática de una entrega en progreso.
5. Validar readiness HTTPS, login/roles, cirugías existentes, mismo contenedor y
   volumen DB, logs sin secretos y registros de backup/verification.txt.
   La renovación de Let's Encrypt continúa bajo la configuración existente.

## 6. Recuperación y límites

Ante fallo de backup, migración, grants o salud local después de detener servicios,
si el esquema coincide con el anterior se recuperan API/web del current.env
anterior. current.env solo se reemplaza tras éxito, y previous.env conserva el
estado anterior. Fallos de pull/head/schema previos no detienen servicios.

Una migración nueva se bloquea antes de detener escritores: necesita ventana y
plan de compatibilidad aprobados. Si el esquema cambia inesperadamente o no puede
consultarse, no hay downgrade/restauración automática: intervención administrativa,
conservar respaldo y evitar sobreescribir datos nuevos. El script no promete
revertir cambios arbitrarios sobre datos realizados por código de mantenimiento.

Un fallo del chequeo HTTPS externo después de SSH marca el job fallido, pero no
revierte automáticamente un release que ya aprobó salud local. Revisar DNS/TLS/SG
con el administrador; no modificar Nginx automáticamente ni restaurar PostgreSQL.
Para revertir un release ya aceptado, revisar previous.env, compatibilidad de
esquema y ejecutar el script protegido desde consola administrativa con ese SHA
solo tras autorización. El workflow manual exige SHA main actual y no sirve para
seleccionar automáticamente un commit histórico.

## Validación de esta preparación

| Comprobación local | Resultado |
|---|---|
| Suite completa con PostgreSQL temporal real | 80 aprobadas, 0 omitidas; concurrencia y permisos incluidos |
| Alembic antes/después de suite y seed idempotente | Aprobados |
| Pruebas específicas entrega/gates | 20 aprobadas (subconjunto de las 80; Docker/HTTP simulados) |
| Respaldo real sobre PostgreSQL ficticio temporal con Compose | Dump y globals generados, SHA-256 correcto; restauración DB aislada y siete tablas idénticas |
| Actionlint, ShellCheck, Bash y git diff --check | Aprobados |

Las pruebas de entrega cubren ruta de producción, backup antes de mantenimiento,
fallos de pull/head/backup/migración/grants/readiness, release activo incompatible,
bloqueo de recuperación al cambiar esquema y conservación de configuración/tag DB.
La recuperación automática se ensayó mediante simulación, no en una EC2 real.
El ensayo de backup usa una composición local temporal con los mismos servicios
DB/maintenance, no el volumen de producción. globals.sql se genera y valida por
checksum; no se restauran automáticamente roles ni credenciales existentes.
Se observa un warning conocido de deprecación TestClient/HTTPX; no se ocultó.
Los logs privados reproducibles quedan en backups/cd-production-validation,
ignorados por Git; no incluyen datos del servidor AWS.

No se ejecutó este código en EC2 ni se activó CD; no declarar despliegue automático
operativo hasta completar una ejecución real autorizada y comprobar sus datos.
