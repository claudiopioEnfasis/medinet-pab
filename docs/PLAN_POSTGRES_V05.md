# Plan de separación PostgreSQL — aplicado con autorización

Aplicado el 30-10-2026 tras autorización explícita del usuario. La API original
ya usa el rol restringido y los tres servicios están saludables. Se preservaron
cuentas existentes, contraseñas, JWT, registros, contenedor DB y volumen.
El respaldo fresco se restauró y verificó antes de cambiar privilegios.

1. Respaldo privado completado en `backups/20261030T160814369837892`:
   `pg_dump -Fc`, roles globales, SHA-256 y restauración real aislada. Las siete
   tablas coinciden fila a fila por huellas; el contenedor de restauración está detenido.
2. Conservar el superusuario, su contraseña, propietarios y usuarios de la aplicación.
   No eliminar roles, registros ni volúmenes. No sobrescribir `.env`.
3. Crear un rol nuevo `medinet_runtime`, LOGIN, sin SUPERUSER, CREATEDB, CREATEROLE,
   REPLICATION ni BYPASSRLS, contraseña aleatoria de 64 caracteres y SCRAM-SHA-256.
4. Otorgar CONNECT, USAGE del esquema, SELECT/INSERT/UPDATE de tablas de negocio,
   INSERT/SELECT de la relación cirugía-equipo y USAGE de sus secuencias. En
   `app_users`, solo SELECT y UPDATE de los contadores de login; sin permisos para
   crear usuarios ni cambiar hashes, roles o activación. Sin DELETE, DDL ni acceso
   de escritura a Alembic. Retirar CREATE del esquema public a PUBLIC (impacta
   únicamente la capacidad de otros roles ordinarios de crear objetos allí).
   Retirar también TEMPORARY de PUBLIC en esta BD; runtime no necesita tablas
   temporales. Verificar que runtime no pertenezca a otros roles.
5. Guardar solo la conexión runtime en `.env.runtime`, archivo nuevo privado
   0600 e ignorado por Git/Docker. La API recibe únicamente esa conexión; JWT se inyecta desde `.env` sin cambiarlo.
   `.env` sigue reservado para administración/migraciones y no se modifica.
6. Retirar Alembic del arranque del servidor. Añadir servicio de mantenimiento
   con perfil explícito para migrar y crear usuarios con la conexión administrativa.
   Después de cada migración se reaplican permisos a tablas conocidas; una tabla
   nueva exige revisión explícita. No otorgar privilegios globales futuros.
7. Ensayar primero en PostgreSQL aislado: migración, denegación de DDL/cambios de
   usuarios, login, lecturas, programación y transiciones con rol restringido.
8. Cambiar la API local solo tras autorización, reconstruir y verificar salud,
   conteos, huellas, UID, permisos y `.env` idéntico. Habrá un breve reinicio de API.
   Conservar imágenes anteriores. Reversión: volver a la configuración anterior
   y conexión administrativa original; no restaurar ni reemplazar datos para ello.

La contraseña administrativa débil requiere una rotación posterior coordinada:
verificar acceso alternativo, respaldar configuración privada, ejecutar ALTER ROLE
por canal privado y actualizar la configuración administrativa de forma atómica.
No se hará esa rotación aquí porque implicaría cambiar el `.env` existente. La
separación elimina esa credencial del backend; no corrige su fortaleza residual.
