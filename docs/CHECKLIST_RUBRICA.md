# Rúbrica EVA 02 — checklist de evidencia (Módulo PAB)

## 1. Backend, BD, Swagger
- [x] Endpoints REST funcionales para quirófanos, pacientes ficticios, profesionales ficticios y cirugías.
- [x] Estados y validación triple: sala, paciente, equipo médico.
- [x] Modelo relacional con llaves, índices, restricciones y puente `surgery_staff`.
- [x] Swagger interactivo y respuestas HTTP documentadas.
- [x] Validaciones Pydantic; acceso y permisos en backend.
- [ ] Capturas reales de Swagger + respuesta 201, 401, 403, 409 y 422.

## 2. Docker seguro
- [x] Docker multi-stage Alpine; API y web sin root; `cap_drop`, `no-new-privileges`.
- [x] PostgreSQL en red interna, volumen persistente, variables `.env` fuera de Git.
- [ ] Captura de `docker compose ps` y redes/volumen.

## 3. AWS EC2 — v1.0
- [ ] EC2 operativa en AWS Academy y Security Group restringido.
- [ ] Enlace público HTTPS; solo web/proxy publicado; DB privada.
- [ ] Captura y prueba de acceso desde otra máquina.

## 4. CI/CD
- [x] Workflow: tests, builds, Bandit/pip-audit, Trivy, GHCR, etapa deploy preparada.
- [ ] Evidencia real de jobs exitosos en GitHub Actions; corregir escaneos si fallan.
- [ ] Habilitar y comprobar despliegue automático en AWS EC2 (v1.0).

## 5. Informe ISO 27034 / OWASP — v1.0
- [ ] Informe formal con arquitectura, modelo entidad relación y decisiones ISO 27034.
- [ ] Matriz de amenazas OWASP Top 10 aplicadas a módulo PAB y pruebas.
- [ ] Capturas/evidencia de todos los apartados.

**Nota:** una casilla [x] de implementación no equivale a evidencia en AWS ni a una validación externa. Los resultados deben medirse en el entorno del usuario.
