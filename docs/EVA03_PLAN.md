# EVA 03 — Plan de arquitectura Multi-AZ y trazabilidad de evidencias

| Campo | Valor |
|---|---|
| Asignatura | Desarrollo Seguro (CI3064) |
| Evaluación | EVA 03 (30% de la nota semestral) |
| Criterios evaluados | 2.1.4, 2.1.5 y 2.1.6 |
| Repositorio | `medinet-pab` (módulo MediNet-Core — MediNet PAB) |
| Infraestructura como código | `terraform/` (provider `hashicorp/aws ~> 5.60`) |
| Pipeline de escaneo | `.github/workflows/iac-security.yml` (Checkov + tfsec + `terraform validate`) |
| Estado del documento | Plan técnico; las evidencias de ejecución se listan como pendientes en la sección 6 |

Este documento es la referencia citada por los comentarios `#checkov:skip` y `#tfsec:ignore` de
`terraform/` y por `terraform/terraform.tfvars.example`. Su objetivo es explicar **por qué** cada
supresión es aceptable en este laboratorio, **qué** componentes forman la arquitectura Multi-AZ y
**qué** falta para cerrar la evaluación. No sustituye al informe técnico de la EVA 03 (sección 5 de
la pauta: STRIDE, normativa de salud, análisis de hallazgos).

---

## 1. Objetivo de la EVA 03 y criterios 2.1.4 / 2.1.5 / 2.1.6

### 1.1 Objetivo

Evolucionar el módulo asignado de MediNet-Core hacia una arquitectura de **alta disponibilidad
Multi-AZ en AWS Academy**, aprovisionada **íntegramente mediante Infraestructura como Código**
(Terraform), con:

- balanceo de carga con **Application Load Balancer (ALB)** sobre un **FQDN** y un **certificado
  SSL/TLS válido** (sin certificados autofirmados);
- base de datos relacional gestionada (**Amazon RDS PostgreSQL**) privada, cifrada y Multi-AZ;
- protección criptográfica de datos clínicos sensibles;
- pruebas de amenazas y vulnerabilidades en ambiente controlado (DAST, failover y ataque controlado);
- escaneo estático de la infraestructura **antes del despliegue** integrado en el pipeline.

Restricción transversal de la pauta: **prohibida la creación o modificación manual de recursos por
consola** (VPC, subredes en 2 AZ, tablas de ruteo, IGW/NAT, Security Groups, ALB, EC2 y RDS) y
**prohibido** exponer credenciales, llaves privadas o contraseñas de base de datos en texto plano en
el repositorio.

### 1.2 Criterios

| Criterio | Exigencia de la pauta | Dónde se aborda en este repositorio |
|---|---|---|
| **2.1.4** — Protección de datos clínicos sensibles, sesiones y lógica de seguridad | Cifrado en tránsito (TLS 1.2/1.3) y en reposo; ocultamiento de *stack traces* y enmascaramiento de datos en logs y respuestas; cabeceras `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options` y CORS restrictivo; validación de autorización con JWT; y, operando con **varios nodos de backend en paralelo contra RDS**, conservar ACID, inmutabilidad de eventos de auditoría, validación real de MIME/extensiones, hashing Argon2/Bcrypt y bloqueo de cuenta. | Capa de red y datos en `terraform/security.tf`, `terraform/database.tf` (TLS en el ALB, RDS cifrada y privada); controles de aplicación en `app/`, `compose.aws.yaml` y sus pruebas. |
| **2.1.5** — Informe técnico y normativa de salud | Diagrama y explicación de la arquitectura Multi-AZ, flujo de aprovisionamiento IaC, modelado de amenazas **STRIDE**, análisis comparativo de **Ley N° 20.584**, **Ley N° 19.628 / 21.719**, **HIPAA**, **HL7/FHIR** e **ISO/IEC 27799**, vinculado a mecanismos técnicos concretos del módulo. | Sección 2 y 3 de este documento (topología y flujo IaC) como insumo; el análisis normativo y STRIDE pertenecen al informe técnico de la evaluación. |
| **2.1.6** — Análisis de amenazas y vulnerabilidades en ambiente controlado | DAST contra el FQDN en HTTPS (por ejemplo OWASP ZAP o Nuclei) corrigiendo hallazgos críticos/altos; prueba de **failover** apagando una EC2 sin interrupción del servicio ni pérdida de datos; y prueba de ataque controlado sobre la regla de negocio crítica (condiciones de carrera, payloads maliciosos, ejecutables disfrazados, manipulación de tokens/roles) evidenciando su bloqueo. | Topología y comandos de `terraform/outputs.tf` (`comandos_verificacion`) habilitan las pruebas; las evidencias de ejecución figuran en la sección 6. |

### 1.3 Alcance de la infraestructura declarada

`terraform/` cubre el criterio 1 completo (VPC, subredes Multi-AZ, ruteo, IGW/NAT, Security Groups,
ALB, EC2 y RDS) y la parte de infraestructura de los criterios 2.1.4 y 2.1.6. Los controles de
aplicación (cabeceras, JWT, Argon2, auditoría inmutable) viven en el código de la aplicación y se
evidencian en el informe, no en `terraform/`.

---

## 2. Arquitectura Multi-AZ

### 2.1 Prefijo de nombres

Todos los recursos se nombran con `local.name_prefix`, definido en `terraform/locals.tf` como
`"${var.project}-${var.environment}"`. Con los valores por defecto (`project = "medinet-pab"`,
`environment = "eval03"`) el prefijo es **`medinet-pab-eval03`**. En las tablas siguientes se indica
el nombre resultante y, entre paréntesis, la dirección Terraform del recurso.

### 2.2 Topología

```
                              Internet
                                 |
                                 | 80 / 443 (var.allowed_web_cidrs, por defecto 0.0.0.0/0)
                                 v
                 +-------------------------------+
                 |  IGW  aws_internet_gateway.main |
                 +---------------+---------------+
                                 |
        +------------------------+------------------------+
        |  Subred publica AZ-a   |  Subred publica AZ-b    |
        |  10.20.10.0/24         |  10.20.11.0/24          |
        |                        |                         |
        |  [ ALB aws_lb.main ]<--+--> [ ALB (misma AZ) ]   |   listener 443 HTTPS (ACM)
        |   aws_subnet.public[0] |   aws_subnet.public[1]  |   listener 80  -> 301 HTTPS
        |        NAT Gateway     |                         |
        |     aws_nat_gateway.main (unico, en public[0])   |
        +-----------+------------+-------------------------+
                    |  ruta privada 0.0.0.0/0 -> NAT
        +-----------+------------+-------------------------+
        |  Subred privada AZ-a   |  Subred privada AZ-b    |
        |  10.20.20.0/24         |  10.20.21.0/24          |
        |                        |                         |
        |  EC2 app-1 (8000/8080) |  EC2 app-2 (8000/8080)  |   sin IP publica
        |  aws_instance.app[0]   |  aws_instance.app[1]    |
        |                        |                         |
        |        +-------+-------+                         |
        |                |  DB Subnet Group (2 AZ)          |
        |        [ RDS PostgreSQL Multi-AZ ]                |
        |        aws_db_instance.main (privada, cifrada)    |
        +------------------------+--------------------------+
```

### 2.3 Red y ruteo

| Elemento | Nombre / valor en el código |
|---|---|
| VPC | `medinet-pab-eval03-vpc` — `aws_vpc.main`, CIDR `10.20.0.0/16`, DNS support y hostnames habilitados |
| Zonas de disponibilidad | `local.azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)`; `availability_zone_count = 2` (validación: entre 2 y 3) |
| Subredes públicas | `medinet-pab-eval03-public-<AZ>` — `aws_subnet.public[0..1]`, `10.20.10.0/24` y `10.20.11.0/24`, `map_public_ip_on_launch = false` |
| Subredes privadas | `medinet-pab-eval03-private-<AZ>` — `aws_subnet.private[0..1]`, `10.20.20.0/24` y `10.20.21.0/24` |
| Internet Gateway | `medinet-pab-eval03-igw` — `aws_internet_gateway.main` |
| NAT Gateway | `medinet-pab-eval03-nat` + EIP `medinet-pab-eval03-nat-eip` — `aws_nat_gateway.main` / `aws_eip.nat`, **único**, en `aws_subnet.public[0]` |
| Tabla pública | `medinet-pab-eval03-rt-public` — `aws_route_table.public`, `0.0.0.0/0` → IGW; asociada a las 2 subredes públicas |
| Tabla privada | `medinet-pab-eval03-rt-private` — `aws_route_table.private`, `0.0.0.0/0` → NAT; asociada a las 2 subredes privadas |

### 2.4 Security Groups encadenados

El encadenamiento declarado en `terraform/security.tf` es **Internet → ALB → EC2 → RDS**; no existe
ingreso directo a las instancias ni a la base de datos.

| Capa | Security Group | Ingreso permitido | Egreso permitido |
|---|---|---|---|
| Borde | `medinet-pab-eval03-alb` — `aws_security_group.alb` | TCP 80 y TCP 443 desde `var.allowed_web_cidrs` (por defecto `0.0.0.0/0`) | TCP 8080 y TCP 8000 **solo** hacia `aws_security_group.app` (`aws_vpc_security_group_egress_rule.alb_to_app_web` y `.alb_to_app_api`) |
| Aplicación | `medinet-pab-eval03-app` — `aws_security_group.app` | TCP 8080 (Nginx) y TCP 8000 (FastAPI) **solo** desde `aws_security_group.alb` | TCP 443 y TCP 80 hacia `0.0.0.0/0` (arranque: apt, git clone, GHCR); TCP/UDP 53 y TCP 5432 dentro de `var.vpc_cidr` |
| Datos | `medinet-pab-eval03-db` — `aws_security_group.db` | TCP 5432 **solo** desde `aws_security_group.app` | Sin bloques `egress` declarados |

Nota de diseño: el egreso del SG de aplicación no crea superficie de ataque porque **no hay reglas de
ingreso públicas**: el único origen válido es el SG del ALB. El egreso del SG del ALB se declara como
`aws_vpc_security_group_egress_rule` independiente para evitar un ciclo de referencias con el SG de
aplicación.

### 2.5 Application Load Balancer, listeners y health checks

| Elemento | Configuración en el código |
|---|---|
| ALB | `medinet-pab-eval03-alb` — `aws_lb.main`: `internal = false`, subredes públicas (`aws_subnet.public[*].id`), SG `aws_security_group.alb`, `drop_invalid_header_fields = true`, `desync_mitigation_mode = "defensive"`, `idle_timeout = 60`, `enable_deletion_protection = var.alb_deletion_protection` |
| Listener HTTPS | `medinet-pab-eval03-listener-https` — `aws_lb_listener.https`: puerto 443, `protocol = "HTTPS"`, `ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"`, `certificate_arn = var.certificate_arn`; acción por defecto → target group de frontend |
| Listener HTTP | `medinet-pab-eval03-listener-http` — `aws_lb_listener.http_redirect`: puerto 80, acción `redirect` a 443 con `HTTP_301` |
| Regla de salud | `medinet-pab-eval03-rule-backend-health` — `aws_lb_listener_rule.backend_health`, prioridad 10, rutas `/health` y `/health/ready` → target group de backend |
| Target group frontend | `medinet-pab-eval03-tg-web` — `aws_lb_target_group.frontend`: puerto 8080, health check `local.frontend_health_path` (`/`), intervalo 15 s, timeout 5 s, umbrales 2/3 |
| Target group backend | `medinet-pab-eval03-tg-api` — `aws_lb_target_group.backend`: puerto 8000, health check `local.backend_health_path` (`/health/ready`, consulta a PostgreSQL), intervalo 15 s, timeout 5 s, umbrales 2/3 |
| Registro de nodos | `aws_lb_target_group_attachment.frontend` y `.backend`, `count = var.instance_count`, puertos 8080 y 8000 |

Ambos target groups usan `deregistration_delay = 30`, lo que acorta la salida de un nodo durante la
prueba de failover.

### 2.6 Capa de cómputo

| Elemento | Configuración en el código |
|---|---|
| AMI | `var.ami_id` o, si está vacío, `data.aws_ami.ubuntu` (Ubuntu 24.04 LTS amd64 de Canonical, `099720109477`) |
| Launch template | `aws_launch_template.app`: `instance_type = var.instance_type` (`t3.micro`), `ebs_optimized = true`, monitoring detallado activo, `metadata_options.http_tokens = "required"` (IMDSv2, hop limit 1), disco raíz `/dev/sda1` `gp3` de `var.root_volume_size_gb` (20 GB) **cifrado** |
| Perfil de instancia | `data.aws_iam_instance_profile.lab` sobre `var.lab_instance_profile_name` (`LabInstanceProfile`) — no se crea IAM propio |
| Instancias | `aws_instance.app` con `count = var.instance_count` (2), en `aws_subnet.private[count.index % var.availability_zone_count]` (round-robin: una por AZ), `associate_public_ip_address = false`, SG `aws_security_group.app` |
| Bootstrap | `templates/user_data.sh.tpl`: instala Docker/Compose, clona `var.repo_url` en `/opt/medinet`, escribe `.env` con permisos `0600` y levanta `compose.aws.yaml` (API 8000, web 8080). Solo el nodo `count.index == 0` ejecuta migraciones Alembic |

### 2.7 Capa de datos

| Elemento | Configuración en el código |
|---|---|
| DB Subnet Group | `medinet-pab-eval03-db-subnets` — `aws_db_subnet_group.main` sobre las 2 subredes privadas (`aws_subnet.private[*].id`) |
| Instancia RDS | `medinet-pab-eval03-postgres` — `aws_db_instance.main`: motor `postgres` `var.db_engine_version` (16), clase `db.t3.micro`, 20 GB `gp3` con `max_allocated_storage` 40 GB, `storage_encrypted = true` |
| Alta disponibilidad | `multi_az = var.db_multi_az` (true), `publicly_accessible = false`, `vpc_security_group_ids = [aws_security_group.db.id]` |
| Respaldo y logs | `backup_retention_period = var.db_backup_retention_days` (7), ventana `07:00-09:00`, mantenimiento `sun:09:00-sun:11:00`, `enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]`, `copy_tags_to_snapshot = true` |
| Credenciales | `random_password.db` (32 caracteres, `special = false`) y `random_password.jwt` (48); el secreto JWT se puede sustituir con `var.jwt_secret` |

Ambos nodos EC2 consumen **la misma** instancia RDS (`db_host = aws_db_instance.main.address` inyectado
en `user_data`), lo que garantiza consistencia transaccional entre nodos.

### 2.8 Salidas útiles para la evidencia

`terraform/outputs.tf` publica: `alb_dns_name`, `alb_zone_id`, `url_publica`, `swagger_url`,
`instancias` (ID y AZ de cada nodo), `target_groups`, `rds_endpoint`, `rds_multi_az`,
`security_groups` y `comandos_verificacion`.

---

## 3. Flujo de aprovisionamiento

El orden es obligatorio: el certificado debe estar **emitido y validado** antes del `apply` porque
`aws_lb_listener.https` lo consume en `var.certificate_arn`, y el CNAME del FQDN hacia el ALB solo
puede crearse cuando el ALB ya existe y Terraform publica su `dns_name`.

```
[1] Certificado ACM (validacion DNS)  ->  [2] terraform apply  ->  [3] CNAME del FQDN al ALB
                                                                    [4] verificacion HTTPS + health
```

### Paso 1 — Certificado ACM

1. Solicitar el certificado en **Amazon Certificate Manager en la misma región del ALB**
   (`var.aws_region`, por defecto `us-east-1`); un certificado de otra región no puede asociarse al
   listener.
2. Elegir validación **DNS** y crear en el proveedor DNS del FQDN el registro CNAME de validación que
   ACM entrega (el laboratorio no tiene Route 53; ver sección 5).
3. Esperar el estado `ISSUED` y copiar el ARN. Ese ARN se entrega como `certificate_arn`
   (variable obligatoria, sin valor por defecto).
4. `terraform/terraform.tfvars.example` referencia este paso; la descripción de la variable apunta a
   `scripts/crear_certificado_acm.sh`, archivo que **no está en el repositorio** (ver sección 6).

### Paso 2 — `terraform apply`

```powershell
cd terraform
terraform init
Copy-Item terraform.tfvars.example terraform.tfvars   # completar y NO versionar
terraform fmt -recursive
terraform validate
terraform plan -out eva03.tfplan
terraform apply eva03.tfplan
```

`terraform apply` crea, en orden de dependencias: VPC e IGW → subredes públicas y privadas → NAT y
tablas de ruteo → Security Groups y reglas de egreso → DB Subnet Group → RDS → launch template e
instancias EC2 → ALB, target groups, listeners y registros → `aws_lb_listener_rule.backend_health`.

Al terminar, recuperar el destino del CNAME:

```powershell
terraform output -raw alb_dns_name
```

### Paso 3 — CNAME del FQDN al ALB

Crear en el proveedor DNS del FQDN un registro **CNAME** `var.domain_name` →
`<valor de alb_dns_name>` (el FQDN de ejemplo de la plantilla es `medinet.ejemplo.dedyn.io`). No se usa
registro alias porque el laboratorio no ofrece Route 53. Propagar el cambio y comprobar resolución:

```powershell
Resolve-DnsName medinet.ejemplo.dedyn.io
```

### Paso 4 — Verificación posterior

```powershell
curl.exe -sI  http://<FQDN>                    # 301 Location: https://<FQDN>/
curl.exe -s   https://<FQDN>/health/ready
curl.exe -sI  https://<FQDN>/docs
```

Criterio de éxito: cadena TLS válida sin advertencias, 301 desde 80, `/docs` accesible solo por 443 y
ambos target groups con los 2 nodos en estado `healthy`.

---

## 4. Supresiones de Checkov / tfsec y su justificación técnica

Los comentarios `#checkov:skip=...` y `#tfsec:ignore:...` de `terraform/` existen porque el gate del
pipeline (`--hard-fail-on HIGH` en Checkov, `--minimum-severity HIGH` en tfsec) bloquearía el
despliegue por hallazgos que **no son corregibles en AWS Academy** o que son **falsos positivos de
correlación**. Cada supresión se documenta aquí una por una. Todo lo demás se corrigió en el código
en lugar de suprimirse: TLS 1.3 en el listener, `drop_invalid_header_fields`, redirección 301, IMDSv2,
disco cifrado, RDS privada y cifrada con Multi-AZ, SG encadenados y secretos generados
(`random_password`) sin valores en el repositorio.

### 4.1 `terraform/alb.tf`

| # | Directiva | Recurso | Hallazgo | Justificación técnica | Riesgo residual |
|---|---|---|---|---|---|
| 1 | `#tfsec:ignore:AVD-AWS-0053` | `aws_lb.main` | Balanceador expuesto a Internet | El ALB **es** el borde de la arquitectura y el único punto de entrada público exigido por la pauta. Las instancias no tienen IP pública ni aceptan tráfico que no venga del SG del ALB, y RDS es privada. | Aceptado por diseño. Mitigado con TLS 1.3, `drop_invalid_header_fields` y encadenamiento de SG. |
| 2 | `#checkov:skip=CKV_AWS_91` | `aws_lb.main` | Sin *access logs* del ALB hacia S3 | Habilitar logs exige un bucket S3 con *bucket policy* y permisos que el rol del laboratorio no permite crear. | Sin registro de accesos en el ALB; el tráfico de aplicación queda en los logs de los contenedores. |
| 3 | `#checkov:skip=CKV_AWS_92` | `aws_lb.main` | Sin *access logging* del ELBv2 | Misma causa que CKV_AWS_91: el bucket y su política quedan fuera del alcance del laboratorio. | Ídem. |
| 4 | `#checkov:skip=CKV2_AWS_28` | `aws_lb.main` | ALB público sin WAFv2 asociado | **WAFv2 no está habilitado en el laboratorio de AWS Academy** (requiere permisos y servicios no disponibles en la cuenta de estudiante). | Sin filtrado L7 perimetral. Mitigado por el endurecimiento de la aplicación y el DAST del criterio 2.1.6. |
| 5 | `#checkov:skip=CKV_AWS_2` | `aws_lb_listener.http_redirect` | Listener HTTP sin TLS | El listener del puerto 80 **no sirve contenido**: su única acción es `redirect` a HTTPS con `HTTP_301`. El listener 443 usa `ELBSecurityPolicy-TLS13-1-2-2021-06`. | Nulo: no hay tráfico en claro servido; el 80 solo redirige. |

### 4.2 `terraform/compute.tf`

| # | Directiva | Recurso | Hallazgo | Justificación técnica | Riesgo residual |
|---|---|---|---|---|---|
| 6 | `#tfsec:ignore:AVD-AWS-0028` | `aws_instance.app` | IMDSv1 permitido | **Falso positivo de correlación**: `aws_launch_template.app` define `metadata_options { http_tokens = "required" }` (IMDSv2 obligatorio) y la instancia usa ese launch template con `version = "$Latest"`. tfsec evalúa la instancia aislada y no lee el template asociado. | Nulo: IMDSv2 obligatorio en el template. |
| 7 | `#tfsec:ignore:AVD-AWS-0131` | `aws_instance.app` | Disco raíz sin cifrar | **Falso positivo de correlación**: el `block_device_mappings` del launch template declara `ebs { encrypted = true, volume_type = "gp3" }` para `/dev/sda1`. | Nulo: cifrado en el template. |

### 4.3 `terraform/database.tf`

| # | Directiva | Recurso | Hallazgo | Justificación técnica | Riesgo residual |
|---|---|---|---|---|---|
| 8 | `#checkov:skip=CKV_AWS_161` | `aws_db_instance.main` | Sin autenticación IAM en RDS | La aplicación se conecta con usuario y contraseña generada por `random_password.db` e inyectada en `user_data`; el driver SQL actual no soporta autenticación IAM. | Credencial rotada por Terraform y fuera de Git; sin rotación automática. |
| 9 | `#checkov:skip=CKV_AWS_118` | `aws_db_instance.main` | Sin *enhanced monitoring* | Enhanced monitoring exige un rol IAM (`rds-monitoring-role`) que **AWS Academy no permite crear**; se reutiliza `LabRole`/`LabInstanceProfile` sin permisos de creación de IAM. | Sin métricas de SO de RDS; se conservan los logs `postgresql` y `upgrade` exportados a CloudWatch. |
| 10 | `#checkov:skip=CKV_AWS_353` | `aws_db_instance.main` | Sin Performance Insights | Performance Insights tiene **costo adicional** y el laboratorio opera con presupuesto cero. | Sin análisis de rendimiento por consulta; aceptado en el laboratorio. |
| 11 | `#checkov:skip=CKV_AWS_293` | `aws_db_instance.main` | `deletion_protection` desactivada | `var.db_deletion_protection` tiene por defecto `false` porque el laboratorio debe poder ejecutar `terraform destroy` al cerrar la sesión; `skip_final_snapshot = true` responde a la misma razón. **En producción debe activarse** (`db_deletion_protection = true`). | Riesgo de borrado accidental durante la evaluación; se mitiga con los respaldos de 7 días. |

### 4.4 `terraform/security.tf`

| # | Directiva | Recurso | Hallazgo | Justificación técnica | Riesgo residual |
|---|---|---|---|---|---|
| 12 | `#tfsec:ignore:AVD-AWS-0107` | `aws_security_group.alb` | Ingreso desde `0.0.0.0/0` | El ALB es el único componente público de la arquitectura: 80/443 deben aceptar Internet para el FQDN de la evaluación. El tráfico hacia EC2 y RDS queda restringido por los SG de aplicación y datos. | Superficie de borde esperada; el origen es configurable con `var.allowed_web_cidrs`. |
| 13 | `#checkov:skip=CKV_AWS_260` | `aws_security_group.alb` | Ingreso público al puerto 80 | El puerto 80 es el punto de entrada público obligatorio de la pauta y responde **301 hacia HTTPS**; no publica contenido. | Nulo: solo redirección. |
| 14 | `#tfsec:ignore:AVD-AWS-0104` | `aws_security_group.app` | Egreso hacia `0.0.0.0/0` | El arranque del nodo necesita salir por el NAT para `apt`, `git clone` y *pull* de imágenes desde GHCR (TCP 80/443). No existe ingreso público: las únicas reglas de entrada provienen del SG del ALB, por lo que el egreso abierto no expone superficie de ataque. El resto del egreso está limitado a DNS y PostgreSQL dentro de `var.vpc_cidr`. | Egreso amplio en 80/443; se acota con `var.vpc_cidr` en 53/5432. |
| 15 | `#checkov:skip=CKV_AWS_382` | `aws_security_group.db` | SG sin reglas de egreso declaradas | El SG de RDS no inicia conexiones salientes: solo responde a las sesiones entrantes del SG de aplicación. La regla de egreso por defecto del SG no se usa porque el *firewall* de Security Groups es **stateful**. | Nulo en la práctica: no hay tráfico saliente originado por RDS. |

### 4.5 Resumen

- Supresiones totales: **15** (10 `checkov:skip`, 5 `tfsec:ignore`).
- Falsos positivos de correlación (no requieren acción): #6 y #7.
- Restricciones de AWS Academy (no corregibles en el laboratorio): #2, #3, #4, #9, #10.
- Decisiones de diseño exigidas por la pauta: #1, #5, #12, #13, #14.
- Decisiones de ciclo de vida del laboratorio que deben revertirse en producción: #11.
- Requisito no soportado por la aplicación actual: #8.
- Propiedad del *firewall* stateful: #15.

Todas las supresiones están referenciadas desde el propio código con la ruta `docs/EVA03_PLAN.md`
(secciones 4.1 a 4.4).

---

## 5. Limitaciones del laboratorio AWS Academy

| Limitación | Efecto en el diseño | Evidencia en el repositorio |
|---|---|---|
| Identidad fija `LabRole` / `LabInstanceProfile`; sin permiso para crear roles ni políticas IAM | No se declaran `aws_iam_role` ni `aws_iam_policy`. El perfil se consume con `data.aws_iam_instance_profile.lab` y `var.lab_instance_profile_name` (`LabInstanceProfile`). Esto obliga a suprimir CKV_AWS_118 (rol de enhanced monitoring). | `terraform/compute.tf`, `terraform/variables.tf` |
| Sin Route 53 | El FQDN se resuelve con un **CNAME** hacia `aws_lb.main.dns_name` en el proveedor DNS gratuito del dominio, no con registro alias. La validación del certificado ACM también es manual (registro CNAME de validación). `alb_zone_id` se publica solo como referencia. | `terraform/outputs.tf`, sección 3 de este documento |
| Sin AWS WAFv2 | No se declara `aws_wafv2_web_acl` ni asociación al ALB: es la causa de la supresión CKV2_AWS_28. La mitigación L7 se concentra en la aplicación y en el DAST. | `terraform/alb.tf` |
| Sesión de laboratorio de **4 horas** con credenciales temporales | El despliegue debe completarse y verificarse dentro de la sesión: `terraform apply`, pruebas de failover y `terraform destroy` antes del cierre. El estado queda **local** (`backend "s3" {}` comentado a propósito en `terraform/versions.tf`) y las credenciales caducan con la sesión. `alb_deletion_protection` y `db_deletion_protection` deben quedar en `false` para poder destruir. | `terraform/versions.tf`, `terraform/terraform.tfvars.example` |
| Restricciones de S3/bucket policy | Sin *access logs* del ALB (supresiones CKV_AWS_91 y CKV_AWS_92). | `terraform/alb.tf` |
| Presupuesto del laboratorio | Sin Performance Insights (CKV_AWS_353); RDS en `db.t3.micro` y EC2 en `t3.micro`. | `terraform/database.tf`, `terraform/variables.tf` |
| Un único NAT Gateway (en `aws_subnet.public[0]`) | El egreso de las 2 subredes privadas depende de una sola AZ. Es una decisión de costo del laboratorio, no de la pauta: en producción se despliega un NAT por AZ. | `terraform/network.tf` |
| Sin automatización de la emisión del certificado | `variables.tf` cita `scripts/crear_certificado_acm.sh`, que no existe en `scripts/`; el ARN se entrega manualmente por `certificate_arn`. | Sección 6 |

---

## 6. Evidencias pendientes por criterio

Estado al crear este documento: la infraestructura y el pipeline están escritos, pero **no se han
ejecutado** en la cuenta de AWS Academy ni se han descargado los reportes del pipeline. Nada de la
columna "Evidencia" se considera obtenido hasta que exista el archivo o la captura correspondiente.

### 6.1 Criterio 1 — IaC y escaneo de seguridad

| Evidencia pendiente | Cómo se obtiene | Destino |
|---|---|---|
| `terraform init`/`fmt -check`/`validate` en verde y `.terraform.lock.hcl` versionado | Ejecutar la secuencia de `terraform/README.md` y confirmar el archivo en `git status` | `terraform/.terraform.lock.hcl` en el commit |
| Run del workflow **MediNet PAB - IaC Security** con los 3 jobs en verde (`terraform-validate`, `checkov`, `tfsec`) | GitHub → Actions → seleccionar el run del commit | Captura de pantalla del run |
| Reporte SARIF de Checkov | Descargar el artefacto `checkov-sarif` del run | `EVIDENCIAS/criterio1/` |
| Reporte JSON de tfsec | Descargar el artefacto `tfsec-json` del run | `EVIDENCIAS/criterio1/` |
| Salida de `terraform plan`/`apply` sin errores | `terraform plan -out` y `terraform apply` en la sesión del laboratorio | `EVIDENCIAS/criterio1/` |
| Ausencia de secretos en Git | `git status --short` sin `*.tfvars` ni `*.tfstate`; revisión del commit | Registro en el informe |

### 6.2 Criterio 2.1.4 — Datos clínicos, sesiones y lógica de seguridad

| Evidencia pendiente | Cómo se obtiene |
|---|---|
| TLS 1.2/1.3 y redirección 301 desde 80 | `curl.exe -sI http://<FQDN>` y `curl.exe -sI https://<FQDN>` (cadena de certificado válida) |
| Cabeceras `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options` y CORS restrictivo | `curl.exe -sI https://<FQDN>/` y una petición con `Origin` no permitido |
| `/docs` accesible solo por HTTPS | `curl.exe -sI https://<FQDN>/docs` |
| Cifrado en reposo y aislamiento de RDS | `terraform output rds_multi_az` y `aws rds describe-db-instances --db-instance-identifier medinet-pab-eval03-postgres` (`StorageEncrypted`, `PubliclyAccessible`, `MultiAZ`) |
| Concurrencia ACID y auditoría inmutable con 2 nodos | Prueba de carga contra el FQDN con ambos nodos `healthy` y revisión de eventos de auditoría |
| Hashing Argon2/Bcrypt, bloqueo de cuenta y validación real de MIME | Pruebas de la aplicación (suite `tests/`) y captura de respuestas de rechazo |
| Ocultamiento de *stack traces* y enmascaramiento de datos | Petición que provoque error y revisión de la respuesta y de los logs |

### 6.3 Criterio 2.1.5 — Informe técnico y normativa

| Evidencia pendiente | Cómo se obtiene |
|---|---|
| Diagrama Multi-AZ final | Sección 2 de este documento, exportada al informe |
| Flujo de aprovisionamiento IaC | Sección 3 de este documento, con capturas de `apply` y del CNAME |
| Modelado de amenazas STRIDE del módulo | Elaboración propia sobre el módulo asignado (no existe aún en el repositorio) |
| Comparativa Ley 20.584 / 19.628 / 21.719 / HIPAA / HL7-FHIR / ISO 27799 vinculada a mecanismos concretos | Redacción en el informe técnico |
| Análisis de los hallazgos Checkov/tfsec y de los reportes ZAP | A partir de los artefactos de `EVIDENCIAS/criterio1/` y del DAST |

### 6.4 Criterio 2.1.6 — DAST, failover y ataque controlado

| Evidencia pendiente | Cómo se obtiene |
|---|---|
| Reporte DAST (OWASP ZAP o Nuclei) contra `https://<FQDN>` antes y después de mitigar | Escaneo contra el FQDN y comparación de hallazgos |
| Failover: `tail -f` de peticiones continuas + `stop` de una EC2 + servicio sin caída | `aws ec2 stop-instances --instance-ids <id>` (el `id` lo entrega `terraform output instancias`) mientras se envía tráfico al FQDN |
| Target groups recuperando el estado `healthy` tras el failover | `aws elbv2 describe-target-health --target-group-arn <arn>` (ARN en `terraform output target_groups`) |
| Sin pérdida de datos tras el failover | Consulta a la base antes y después del `stop` |
| Ataque controlado bloqueado (condiciones de carrera, payloads, ejecutable disfrazado, token manipulado) | Guion de pruebas de ataque del módulo y capturas de las respuestas de bloqueo |
| Video o capturas de la demostración | Grabación de la sesión del laboratorio |

### 6.5 Brechas de repositorio a cerrar

| Brecha | Detalle |
|---|---|
| `scripts/crear_certificado_acm.sh` | Citado en la descripción de `var.certificate_arn` (`terraform/variables.tf`) pero ausente en `scripts/`. Mientras no exista, el ARN del certificado se obtiene por consola de ACM y se entrega como variable. |
| `docs/` sin informe EVA 03 | Este documento es el plan técnico; el informe con STRIDE y normativa todavía no está en `docs/`. |
| `EVIDENCIAS/criterio1/` | Directorio de evidencias del criterio 1 fuera del repositorio; debe poblarse con los artefactos del run en verde. |
