# MediNet PAB v0.5 — cambios y verificaciones

Versiones pactadas: **v0.5** reúne anteriores planes v0.4 + v0.5; **v1.0** reunirá despliegue AWS + informe final.

## Backend
- Migración base Alembic versionada `0001`.
- Inicio del contenedor ejecuta migración, en vez de `Base.metadata.create_all`.
- Compatibilidad de bases v0.3 existentes con validación previa de tablas/columnas: `scripts/migrate.py`.
- `/health/ready` comprueba conexión SQL real.
- OpenAPI enriquecido con 401/403/404/409/422.
- Refresco de estado posterior al bloqueo transaccional para evitar transiciones concurrentes basadas en datos obsoletos.
- Se agregaron 8 pruebas de regresión SQLite, 2 pruebas automáticas de migración y 1 prueba PostgreSQL concurrente (se ejecuta con `TEST_DATABASE_URL`).

## Frontend
- Nueva portada operativa: identidad visual verde bosque/petróleo, hero de control, visual de ocupación de salas y métricas reales.
- Tarjetas de pabellones con ilustración geométrica ligera, más claridad de estados y responsive.
- Nueva composición de login, sin añadir imágenes externas ni bibliotecas de interfaz.
- Actualización Vite 7.1.0 → 7.3.7 (rama con correcciones de seguridad verificadas en octubre 2026).
- Nginx: políticas de seguridad, CSP para app web y limitación de tasa de solicitudes de login (10 req/min por IP, burst 6).

## CI/CD
- Workflow `.github/workflows/ci-cd.yml` cubre pruebas, builds, SAST/SCA, Trivy y publicación GHCR por SHA.
- Despliegue EC2 condicionado a `ENABLE_EC2_DEPLOY=true`: se mantiene apagado hasta v1.0.
- Se deja `compose.prod.yaml` para su integración en EC2, sin exponer el backend ni PostgreSQL.

## Verificación de este entorno de generación
- **32 pruebas locales pasaron, 1 prueba PostgreSQL omitida** porque no existe PostgreSQL/Docker disponible en este entorno.
- Migración inicial en SQLite desde BD vacía: **correcta**; `alembic check`: **sin divergencias**.
- Simulación de migración v0.3 con datos: **correcta**, se conservaron los registros.
- JS/JSX parseado sintácticamente con parser TypeScript: **sin errores**.
- YAML de CI y Compose: **válido como YAML**, no como ejecución real.
- `npm install` no se pudo ejecutar aquí por bloqueo DNS al registro de npm. Debes comprobar build React y Nginx con `docker compose up --build -d` en tu PC y revisar la pestaña **Actions** en GitHub.
- Ningún despliegue AWS se declara ejecutado.
