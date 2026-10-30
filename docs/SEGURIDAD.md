# Seguridad y consideraciones ISO 27034 / OWASP

**Documento de diseño, no certificación.** El informe final se construirá en v1.0 con resultados y capturas comprobadas.

| Riesgo del módulo | Control y evidencia esperada |
|---|---|
| Broken Access Control (OWASP A01) | JWT y RBAC en servidor, tests 401/403, roles admin/coordinator/viewer. |
| Security Misconfiguration | Nginx sin root; límites login; Docker `cap_drop` y redes; AWS Security Groups en v1.0. |
| Injection (A03) | SQLAlchemy enlaza parámetros, validación Pydantic; prueba de referencia maliciosa 422. |
| Insecure Design | Triple disponibilidad con bloqueo de recurso PostgreSQL; prueba de dos cirugías concurrentes. |
| Vulnerable Components | SCA pip-audit/npm, Trivy imágenes; renovar dependencias cuando reporte hallazgos. |
| Authentication Failures | Argon2id, JWT 30 minutos, bloqueo cuenta, límite Nginx por IP, no persistencia de token en navegador. |
| Logging/Monitoring Failures | Por completar: trazabilidad estructurada y correlación del módulo AUD (de otro grupo). |
| Data Integrity / Concurrency | Respuestas 409 y transacciones SQL; controles de transición de estados. |

**ISO 27034 (enfoque de ciclo de vida):** requisitos de seguridad del módulo → diseño de controles (RBAC, confidencialidad, prevención de doble reserva) → implementación y endurecimiento → pruebas CI/CD → verificación de despliegue → evidencias e informe. Los elementos pendientes deben registrarse como riesgos abiertos, no como controles ya comprobados.

**Límites conocidos:** la autenticación es local de demostración, no está enlazada con el módulo IAM del grupo correspondiente; no existe auditoría inmutable distribuida; despliegue local sin HTTPS; la verificación real de carrera PostgreSQL y de imágenes Docker se realizará en CI. Nunca utilizar pacientes reales.
