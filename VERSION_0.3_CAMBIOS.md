# MediNet PAB · Resumen de v0.3

**Principal novedad:** autenticación local y permisos por roles. El frontend, el backend y PostgreSQL continúan en contenedores separados.

1. Actualizar sin borrar `postgres_data`.
2. Agregar `JWT_SECRET` al `.env` ya existente (generarlo con `openssl rand -hex 32`).
3. Ejecutar `docker compose up --build -d`.
4. Crear el usuario admin con `docker compose exec -it api python -m scripts.create_user admin admin`.
5. Abrir http://localhost:3000, iniciar sesión y comprobar permisos.

**Estado de validación:** 22 tests automatizados del backend con SQLite pasaron en el entorno de preparación. La compilación de React / Docker y el despliegue AWS quedan pendientes de validar en el equipo de desarrollo.

**No usar pacientes reales ni publicar la demo en Internet.**
