terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # EVA 03: backend local a propósito.
  # El estado contiene la contraseña de RDS y el secreto JWT; queda fuera de Git
  # (.gitignore ignora *.tfstate) y no se comparte. Para trabajo en equipo,
  # habilitar un backend S3 cifrado (ver README, sección "Estado remoto").
  # backend "s3" {}
}
