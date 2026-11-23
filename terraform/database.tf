# Amazon RDS PostgreSQL gestionada, privada, Multi-AZ y cifrada en reposo.

resource "random_password" "db" {
  length  = 32
  special = false # RDS rechaza / @ " y espacio en la contraseña maestra.
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "aws_db_subnet_group" "main" {
  name        = "${local.name_prefix}-db-subnets"
  description = "Subredes privadas en 2 AZ para RDS Multi-AZ"
  subnet_ids  = aws_subnet.private[*].id

  tags = { Name = "${local.name_prefix}-db-subnets" }
}

resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  allocated_storage     = var.db_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  max_allocated_storage = var.db_allocated_storage_gb * 2

  # Alta disponibilidad y aislamiento de red.
  multi_az               = var.db_multi_az
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]

  backup_retention_period = var.db_backup_retention_days
  backup_window           = "07:00-09:00"
  maintenance_window      = "sun:09:00-sun:11:00"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade = true
  apply_immediately          = true
  deletion_protection        = var.db_deletion_protection

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  #checkov:skip=CKV_AWS_161:La aplicacion usa autenticacion por contrasena generada; IAM auth no es compatible con el driver actual; Justificacion: docs/EVA03_PLAN.md seccion 4.
  #checkov:skip=CKV_AWS_118:Enhanced monitoring requiere rol IAM que AWS Academy no permite crear; Justificacion: docs/EVA03_PLAN.md seccion 4.
  #checkov:skip=CKV_AWS_353:Performance Insights tiene costo adicional en el laboratorio; Justificacion: docs/EVA03_PLAN.md seccion 4.

  #checkov:skip=CKV_AWS_293:Entorno de laboratorio: se requiere terraform destroy; produccion debe activar db_deletion_protection; Justificacion: docs/EVA03_PLAN.md seccion 4.

  skip_final_snapshot = true

  tags = { Name = "${local.name_prefix}-postgres", Tier = "data" }
}
