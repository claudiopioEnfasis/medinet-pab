locals {
  name_prefix = "${var.project}-${var.environment}"
  azs         = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  # El secreto JWT se genera si no se entrega uno por variable.
  jwt_secret = var.jwt_secret != "" ? var.jwt_secret : random_password.jwt.result

  # Rutas de salud que el ALB usa contra el backend (FastAPI las expone en la raíz).
  backend_health_path  = "/health/ready"
  frontend_health_path = "/"

  tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Evaluacion  = "EVA03-CI3064"
      DataClass   = "clinica-sensible"
    },
    var.tags,
  )
}
