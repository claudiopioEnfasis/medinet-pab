terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "domain_name" {
  description = "Nombre público exacto de la aplicación, sin comodín ni punto final."
  type        = string

  validation {
    condition = (
      length(var.domain_name) <= 253 &&
      can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", var.domain_name))
    )
    error_message = "Usa un FQDN en minúsculas, sin comodín ni punto final."
  }
}

resource "aws_acm_certificate" "app" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = {
    Project     = "medinet-pab"
    Environment = "eval03"
  }

  lifecycle {
    create_before_destroy = true
  }
}

output "certificate_arn" {
  description = "ARN solicitado. No usar en el ALB hasta verificar que ACM indique ISSUED."
  value       = aws_acm_certificate.app.arn
}

output "validation_records" {
  description = "Publicar estos CNAME en el DNS autoritativo para validar ACM."
  value = {
    for record in aws_acm_certificate.app.domain_validation_options : record.domain_name => {
      name  = record.resource_record_name
      type  = record.resource_record_type
      value = record.resource_record_value
    }
  }
}
