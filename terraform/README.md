# Terraform — MediNet PAB Multi-AZ (EVA 03)

## Credenciales de arranque para Agenda/PAB

Antes de aprovisionar, debe existir un `SecureString` en `us-east-1` con la contraseña de `medinet_runtime`. Indica su nombre en `runtime_db_password_parameter` (por defecto, `/medinet-pab/eval03/runtime-db-password`). Usa una contraseña aleatoria de 48 a 128 caracteres ASCII alfanuméricos, `_` o `-`. `LabInstanceProfile` debe poder leer y descifrar ese parámetro específico. Terraform no lee su valor.

El primer nodo usa la cuenta administrativa para aplicar Alembic y aprovisionar o reaplicar los permisos de `medinet_runtime`. La API de ambos nodos usa el rol restringido. En una base existente, el valor del parámetro debe coincidir con la contraseña del rol: el arranque no la rota. Usa una imagen que incluya la revisión `0002` y el script `db_privileges`.

La contraseña administrativa aún se renderiza en el arranque del primer nodo, y el secreto JWT en ambos. Protege el estado y restringe la lectura de `user_data`. **No apliques un plan sobre los nodos existentes sin revisar los reemplazos**: el primer nodo tiene `user_data_replace_on_change` activado.

Infraestructura como código de la arquitectura Multi-AZ: VPC y subredes en 2 Zonas de
Disponibilidad, IGW/NAT, Security Groups encadenados, ALB con TLS (ACM), 2 nodos EC2 privados y
Amazon RDS PostgreSQL Multi-AZ. El detalle de diseño, las supresiones de Checkov/tfsec y las
evidencias pendientes están en [`../docs/EVA03_PLAN.md`](../docs/EVA03_PLAN.md).

## Requisitos

| Herramienta | Versión |
|---|---|
| Terraform | `>= 1.6.0` (el pipeline usa 1.9.8) |
| Provider `hashicorp/aws` | `~> 5.60` |
| Provider `hashicorp/random` | `~> 3.6` |
| Credenciales | Sesión activa de AWS Academy con `LabRole` / `LabInstanceProfile` |

## Variables obligatorias

Estas cuatro variables no tienen valor por defecto: `terraform plan` falla si no se entregan.

| Variable | Descripción | Ejemplo de la plantilla |
|---|---|---|
| `domain_name` | FQDN público que apunta por CNAME al ALB | `medinet.ejemplo.dedyn.io` |
| `certificate_arn` | ARN del certificado ACM **ya emitido y validado** para ese FQDN, en la misma región del ALB | `arn:aws:acm:us-east-1:...:certificate/...` |
| `image_prefix` | Prefijo de imágenes en GHCR, sin `-api`/`-web` | `ghcr.io/claudiopioenfasis/medinet-pab` |
| `image_tag` | Etiqueta publicada por CI para ese commit | `sha-0000...` |

Variables opcionales con valor por defecto relevante: `aws_region` (`us-east-1`), `project`
(`medinet-pab`), `environment` (`eval03`), `availability_zone_count` (2, validado entre 2 y 3),
`instance_count` (2, mínimo 2), `instance_type` (`t3.micro`), `db_instance_class` (`db.t3.micro`),
`db_multi_az` (`true`), `lab_instance_profile_name` (`LabInstanceProfile`), `allowed_web_cidrs`
(`["0.0.0.0/0"]`).

Variables sensibles (`sensitive = true`, nunca en archivos versionados):

```powershell
$env:TF_VAR_ghcr_token = "<token de lectura de GHCR>"   # solo si las imágenes son privadas
$env:TF_VAR_jwt_secret = "<secreto de al menos 32 caracteres>"  # vacío = se genera aleatoriamente
```

`terraform.tfvars.example` es la plantilla; copiarla a `terraform.tfvars` (ignorado por Git).

## Orden de apply

El certificado ACM se emite **antes** del `apply` (el listener 443 lo consume) y el CNAME del FQDN
se crea **después**, cuando Terraform publica el `dns_name` del ALB.

```powershell
cd terraform

# 1. Dependencias y formato
terraform init
terraform fmt -recursive

# 2. Validacion estatica (no necesita credenciales)
terraform validate

# 3. Plan revisable
terraform plan -out eva03.tfplan

# 4. Aprovisionamiento
terraform apply eva03.tfplan

# 5. Destino del CNAME del FQDN
terraform output -raw alb_dns_name
```

Paso 5 es la entrada del registro **CNAME** `domain_name` → `alb_dns_name` en el proveedor DNS del
dominio (el laboratorio no tiene Route 53). Después de propagar el DNS, verificar por HTTPS.

Para destruir el laboratorio al cerrar la sesión (4 h): `alb_deletion_protection` y
`db_deletion_protection` deben estar en `false`, y luego `terraform destroy`.

## Comandos de verificación

```powershell
# Salidas de la infraestructura
terraform output
terraform output -raw url_publica
terraform output -raw rds_multi_az          # debe ser true
terraform output -json instancias           # 2 nodos en AZ distintas
terraform output -json security_groups

# Borde: redireccion 80 -> 301 y TLS valido en 443
curl.exe -sI http://<FQDN>
curl.exe -s  https://<FQDN>/health/ready
curl.exe -sI https://<FQDN>/docs

# ALB: ambos target groups con los nodos healthy
aws elbv2 describe-target-health --target-group-arn <arn-frontend>
aws elbv2 describe-target-health --target-group-arn <arn-backend>

# RDS: privada, cifrada y Multi-AZ
aws rds describe-db-instances --db-instance-identifier medinet-pab-eval03-postgres `
  --query "DBInstances[0].[MultiAZ,PubliclyAccessible,StorageEncrypted,DBSubnetGroup.SubnetGroupStatus]"

# EC2: sin IP publica y en subredes privadas
aws ec2 describe-instances --filters "Name=tag:Project,Values=medinet-pab" `
  --query "Reservations[].Instances[].[InstanceId,Placement.AvailabilityZone,PublicIpAddress,SubnetId]"

# Failover (criterio 2.1.6): detener un nodo y comprobar continuidad
aws ec2 stop-instances --instance-ids <id-de-terraform-output-instancias>
```

Comprobación local del criterio 1 sin credenciales de AWS:

```powershell
python ..\scripts\verificar_criterio1_tf.py
```

## Advertencia sobre `tfstate` y `tfvars`

- El estado de Terraform contiene **la contraseña de RDS** (`random_password.db`) y **el secreto
  JWT** en texto plano, además de todos los identificadores de la infraestructura.
- `terraform.tfstate`, `terraform.tfstate.*`, `.terraform/`, `*.tfplan` y `terraform.tfvars` están
  en `.gitignore`. **No forzar su inclusión**: si aparecen en `git status`, algo se versionó mal.
- El backend remoto está deshabilitado a propósito (`backend "s3" {}` comentado en `versions.tf`)
  porque el laboratorio no permite crear el bucket ni su política. En un entorno real se habilita un
  backend S3 **cifrado y con bloqueo de estado**, y los secretos se mueven a Secrets Manager.
- `terraform.tfvars` y los valores de `TF_VAR_*` nunca se comparten por Git, chat ni capturas de
  pantalla. La plantilla versionada (`terraform.tfvars.example`) solo contiene valores de ejemplo.
- `.terraform.lock.hcl` **sí** se versiona: fija las versiones y los hashes de los providers.
