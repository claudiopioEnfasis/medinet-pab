provider "aws" {
  region = var.aws_region

  # Etiquetado obligatorio de todo recurso, sin repetirlo en cada bloque.
  default_tags {
    tags = local.tags
  }
}

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}
