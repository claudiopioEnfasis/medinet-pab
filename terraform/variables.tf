# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------
variable "aws_region" {
  description = "Región de AWS Academy. us-east-1 es la más usada en laboratorios."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Nombre corto del proyecto (prefijo de todos los recursos)."
  type        = string
  default     = "medinet-pab"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project))
    error_message = "project debe empezar con letra minúscula y usar solo minúsculas, números y guiones."
  }
}

variable "environment" {
  description = "Sufijo de entorno (eval03, lab, prod...)."
  type        = string
  default     = "eval03"
}

variable "tags" {
  description = "Etiquetas adicionales para todos los recursos."
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zone_count" {
  description = "Cantidad de Zonas de Disponibilidad (la pauta exige mínimo 2)."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "La arquitectura Multi-AZ exige entre 2 y 3 zonas de disponibilidad."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR por subred pública (una por AZ)."
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR por subred privada (una por AZ), usada por EC2 y RDS."
  type        = list(string)
  default     = ["10.20.20.0/24", "10.20.21.0/24"]
}

# ---------------------------------------------------------------------------
# Borde (ALB + FQDN + TLS)
# ---------------------------------------------------------------------------
variable "domain_name" {
  description = "FQDN público que apunta al ALB, por ejemplo medinet.algo.dedyn.io."
  type        = string
}

variable "certificate_arn" {
  description = "ARN del certificado ACM ya emitido y validado para domain_name (ver terraform/acm/README.md)."
  type        = string
}

variable "allowed_web_cidrs" {
  description = "Orígenes permitidos en 80/443 del ALB. Mantener 0.0.0.0/0 para el FQDN público de la evaluación."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "alb_deletion_protection" {
  description = "Protección de borrado del ALB. Desactivar solo para terraform destroy."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Cómputo
# ---------------------------------------------------------------------------
variable "instance_type" {
  description = "Tipo de instancia para los nodos de aplicación."
  type        = string
  default     = "t3.micro"
}

variable "instance_count" {
  description = "Cantidad de nodos EC2 (mínimo 2, en AZ distintas)."
  type        = number
  default     = 2

  validation {
    condition     = var.instance_count >= 2
    error_message = "La pauta exige al menos 2 instancias EC2 en Zonas de Disponibilidad distintas."
  }
}

variable "lab_instance_profile_name" {
  description = "Instance profile de AWS Academy. No se crea IAM: se reutiliza el del laboratorio."
  type        = string
  default     = "LabInstanceProfile"
}

variable "ami_id" {
  description = "AMI explícita. Vacío = Ubuntu 24.04 LTS amd64 más reciente de Canonical."
  type        = string
  default     = ""
}

variable "root_volume_size_gb" {
  description = "Tamaño del disco raíz cifrado de cada nodo."
  type        = number
  default     = 20
}

# ---------------------------------------------------------------------------
# Aplicación (imágenes publicadas por CI)
# ---------------------------------------------------------------------------
variable "image_prefix" {
  description = "Prefijo de imágenes en GHCR, sin -api/-web. Ej: ghcr.io/usuario/medinet-pab."
  type        = string
}

variable "image_tag" {
  description = "Etiqueta de las imágenes (sha-<commit> publicado por CI)."
  type        = string
}

variable "repo_url" {
  description = "Repositorio que los nodos clonan para obtener compose.aws.yaml."
  type        = string
  default     = "https://github.com/claudiopioEnfasis/medinet-pab.git"
}

variable "repo_branch" {
  description = "Rama que clonan los nodos."
  type        = string
  default     = "main"
}

variable "ghcr_user" {
  description = "Usuario de GitHub para docker login en GHCR (vacío si las imágenes son públicas)."
  type        = string
  default     = ""
}

variable "ghcr_token" {
  description = "Token de lectura de GHCR. Nunca versionar: pasar por TF_VAR_ghcr_token."
  type        = string
  default     = ""
  sensitive   = true
}

variable "jwt_secret" {
  description = "Secreto de firma JWT (>=32 caracteres). Vacío = se genera aleatoriamente."
  type        = string
  default     = ""
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
variable "db_name" {
  description = "Nombre de la base PostgreSQL."
  type        = string
  default     = "medinet_pab"
}

variable "db_username" {
  description = "Usuario administrador de RDS."
  type        = string
  default     = "medinet_admin"
}

variable "runtime_db_password_parameter" {
  description = "Nombre del SecureString preexistente para medinet_runtime. No contiene su valor."
  type        = string
  default     = "/medinet-pab/eval03/runtime-db-password"

  validation {
    condition     = can(regex("^(/[A-Za-z0-9_.-]+)+$", var.runtime_db_password_parameter))
    error_message = "Indica una ruta absoluta de Parameter Store sin espacios."
  }
}

variable "db_instance_class" {
  description = "Clase de la instancia RDS."
  type        = string
  default     = "db.t3.micro"
}

variable "db_engine_version" {
  description = "Versión mayor de PostgreSQL gestionada por RDS."
  type        = string
  default     = "16"
}

variable "db_allocated_storage_gb" {
  description = "Almacenamiento inicial de RDS en GB."
  type        = number
  default     = 20
}

variable "db_multi_az" {
  description = "Habilita standby Multi-AZ en RDS (la pauta lo exige)."
  type        = bool
  default     = true
}

variable "db_backup_retention_days" {
  description = "Días de respaldo automático (mínimo 7 recomendado por la rúbrica)."
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Protección de borrado de RDS. Desactivar solo para terraform destroy en el laboratorio."
  type        = bool
  default     = false
}
