# Nodos EC2 en subredes privadas, uno por Zona de Disponibilidad.
# Sin IP pública y con Security Group que solo acepta tráfico del ALB.

data "aws_ami" "ubuntu" {
  count       = var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu[0].id
}

data "aws_iam_instance_profile" "lab" {
  name = var.lab_instance_profile_name
}

resource "aws_launch_template" "app" {
  name_prefix   = "${local.name_prefix}-"
  image_id      = local.ami_id
  instance_type = var.instance_type
  ebs_optimized = true

  iam_instance_profile {
    name = data.aws_iam_instance_profile.lab.name
  }

  monitoring {
    enabled = true
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 obligatorio
    http_put_response_hop_limit = 1
  }

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      volume_size           = var.root_volume_size_gb
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tpl", {
    image_prefix   = var.image_prefix
    image_tag      = var.image_tag
    db_host        = aws_db_instance.main.address
    db_name        = var.db_name
    db_user        = var.db_username
    db_password    = random_password.db.result
    jwt_secret     = local.jwt_secret
    ghcr_user      = var.ghcr_user
    ghcr_token     = var.ghcr_token
    repo_url       = var.repo_url
    repo_branch    = var.repo_branch
    run_migrations = false
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${local.name_prefix}-app", Tier = "app" }
  }

  tags = { Name = "${local.name_prefix}-lt" }
}

# IMDSv2 obligatorio (http_tokens = required) y disco raiz gp3 cifrado estan
# definidos en aws_launch_template.app; tfsec evalua la instancia de forma
# aislada y no correlaciona el launch template asociado.
# Justificacion y referencia: docs/EVA03_PLAN.md seccion 4.
#tfsec:ignore:AVD-AWS-0028
#tfsec:ignore:AVD-AWS-0131
resource "aws_instance" "app" {
  count = var.instance_count

  # Distribución round-robin: con instance_count >= 2 cada AZ recibe un nodo.
  subnet_id = aws_subnet.private[count.index % var.availability_zone_count].id

  vpc_security_group_ids = [
    aws_security_group.app.id,
  ]

  # Sin IP pública: el único ingreso es el ALB.
  associate_public_ip_address = false

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  # Solo el primer nodo aplica migraciones, para evitar carreras en el esquema.
  user_data = count.index == 0 ? base64encode(templatefile("${path.module}/templates/user_data.sh.tpl", {
    image_prefix   = var.image_prefix
    image_tag      = var.image_tag
    db_host        = aws_db_instance.main.address
    db_name        = var.db_name
    db_user        = var.db_username
    db_password    = random_password.db.result
    jwt_secret     = local.jwt_secret
    ghcr_user      = var.ghcr_user
    ghcr_token     = var.ghcr_token
    repo_url       = var.repo_url
    repo_branch    = var.repo_branch
    run_migrations = true
  })) : null

  user_data_replace_on_change = true

  depends_on = [
    aws_db_instance.main,
    aws_lb_listener.https,
  ]

  tags = {
    Name = "${local.name_prefix}-app-${count.index + 1}"
    AZ   = local.azs[count.index % var.availability_zone_count]
  }

  lifecycle {
    ignore_changes = [ami]
  }
}
