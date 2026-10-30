# Arquitectura y modelo de datos de MediNet PAB

```mermaid
flowchart TD
    B[Navegador / React] -->|HTTPS en v1.0; local HTTP| N[Nginx unprivileged :8080]
    N -->|/api| A[FastAPI :8000 / JWT + RBAC]
    A -->|red privada Docker| D[(PostgreSQL 17 / volumen)]
    G[GitHub Actions] -->|Tests + SAST/SCA + build| C[GHCR / imágenes sha]
    C -.->|En v1.0: runner habilitado| E[AWS Academy EC2 / Docker Compose]
```

```mermaid
erDiagram
    OPERATING_ROOMS ||--o{ SURGERIES : aloja
    PATIENTS ||--o{ SURGERIES : paciente
    SURGERIES ||--|{ SURGERY_STAFF : incorpora
    MEDICAL_STAFF ||--o{ SURGERY_STAFF : participa
    APP_USERS {
      int id PK
      string username UK
      string password_hash
      string role
    }
    OPERATING_ROOMS {
      int id PK
      string code UK
      string name
      string status
    }
    PATIENTS {
      int id PK
      string reference UK
      string full_name
    }
    MEDICAL_STAFF {
      int id PK
      string reference UK
      string full_name
      string specialty
    }
    SURGERIES {
      int id PK
      int room_id FK
      int patient_id FK
      string procedure
      string urgency
      string status
      datetime starts_at
      datetime ends_at
    }
    SURGERY_STAFF {
      int surgery_id PK,FK
      int staff_id PK,FK
    }
```

La aplicación bloquea los recursos involucrados con `pg_advisory_xact_lock` en orden consistente dentro de una transacción, comprueba los solapamientos y luego escribe la cirugía. El control de acceso exige JWT y rol admin/coordinator en endpoints mutables; viewer solo consulta. `patients` y `medical_staff` son **simulaciones** hasta integración con otros equipos de MediNet-Core.
