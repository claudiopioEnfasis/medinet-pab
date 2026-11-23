output "alb_dns_name" {
  description = "Nombre DNS del ALB. Es el destino del CNAME del FQDN."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID del ALB (para alias en Route 53 si se habilitara)."
  value       = aws_lb.main.zone_id
}

output "url_publica" {
  description = "URL HTTPS que debe responder con el certificado valido."
  value       = "https://${var.domain_name}"
}

output "swagger_url" {
  description = "Documentacion interactiva publicada solo por HTTPS."
  value       = "https://${var.domain_name}/docs"
}

output "instancias" {
  description = "IDs y AZ de los nodos de aplicacion."
  value = [
    for i, inst in aws_instance.app : {
      id = inst.id
      az = inst.availability_zone
    }
  ]
}

output "target_groups" {
  description = "ARN de los target groups de frontend y backend."
  value = {
    frontend = aws_lb_target_group.frontend.arn
    backend  = aws_lb_target_group.backend.arn
  }
}

output "rds_endpoint" {
  description = "Endpoint privado de RDS (no accesible desde Internet)."
  value       = aws_db_instance.main.endpoint
}

output "rds_multi_az" {
  description = "Confirma que el standby Multi-AZ esta activo."
  value       = aws_db_instance.main.multi_az
}

output "security_groups" {
  description = "IDs de los SG encadenados por capa."
  value = {
    alb = aws_security_group.alb.id
    app = aws_security_group.app.id
    db  = aws_security_group.db.id
  }
}

output "comandos_verificacion" {
  description = "Comandos sugeridos para la evidencia de la evaluacion."
  value       = <<-EOT
    curl -sI http://${var.domain_name}            # 301 -> https
    curl -s https://${var.domain_name}/health/ready
    aws elbv2 describe-target-health --target-group-arn ${aws_lb_target_group.frontend.arn}
    aws elbv2 describe-target-health --target-group-arn ${aws_lb_target_group.backend.arn}
    aws ec2 stop-instances --instance-ids ${aws_instance.app[0].id}   # prueba de failover
  EOT
}
