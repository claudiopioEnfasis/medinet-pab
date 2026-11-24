# Application Load Balancer público con terminación TLS (ACM) y redirección 80 -> 443.

# ALB publico por diseno: es el borde de la arquitectura y las instancias de
# aplicacion no tienen IP publica ni aceptan trafico que no venga de este SG.
# Justificacion y referencia: docs/EVA03_PLAN.md seccion 4.
#tfsec:ignore:AVD-AWS-0053
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.alb_deletion_protection
  drop_invalid_header_fields = true
  desync_mitigation_mode     = "defensive"
  idle_timeout               = 60

  #checkov:skip=CKV_AWS_91:Access logs a S3 requieren bucket policy que AWS Academy restringe; ver docs/EVA03_PLAN.md.
  #checkov:skip=CKV_AWS_92:Idem al anterior; Justificacion: docs/EVA03_PLAN.md seccion 4.
  #checkov:skip=CKV2_AWS_28:WAFv2 no esta habilitado en el laboratorio de AWS Academy; Justificacion: docs/EVA03_PLAN.md seccion 4.

  tags = { Name = "${local.name_prefix}-alb", Tier = "edge" }
}

# ---------------------------------------------------------------------------
# Target groups: frontend (Nginx) y backend (FastAPI)
# ---------------------------------------------------------------------------
resource "aws_lb_target_group" "frontend" {
  name        = "${local.name_prefix}-tg-web"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = local.frontend_health_path
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name_prefix}-tg-web", Tier = "frontend" }
}

resource "aws_lb_target_group" "backend" {
  name        = "${local.name_prefix}-tg-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  deregistration_delay = 30

  # /health/ready consulta a PostgreSQL: si RDS cae, el nodo sale de rotación.
  health_check {
    enabled             = true
    path                = local.backend_health_path
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name_prefix}-tg-api", Tier = "backend" }
}

# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  # El listener TLS cubre las respuestas del frontend y las rutas directas de la API.
  routing_http_response_strict_transport_security_header_value = "max-age=31536000"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = { Name = "${local.name_prefix}-listener-https" }
}

#checkov:skip=CKV_AWS_2:Este listener existe solo para redirigir a HTTPS; no sirve contenido en claro; Justificacion: docs/EVA03_PLAN.md seccion 4.
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = { Name = "${local.name_prefix}-listener-http" }
}

# Expone el health check del backend a través del ALB para evidenciar el
# encadenamiento: /health y /health/ready van directo a FastAPI.
resource "aws_lb_listener_rule" "backend_health" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/health", "/health/ready"]
    }
  }

  tags = { Name = "${local.name_prefix}-rule-backend-health" }
}

# ---------------------------------------------------------------------------
# Registro de los nodos en ambos target groups
# ---------------------------------------------------------------------------
resource "aws_lb_target_group_attachment" "frontend" {
  count = var.instance_count

  target_group_arn = aws_lb_target_group.frontend.arn
  target_id        = aws_instance.app[count.index].id
  port             = 8080
}

resource "aws_lb_target_group_attachment" "backend" {
  count = var.instance_count

  target_group_arn = aws_lb_target_group.backend.arn
  target_id        = aws_instance.app[count.index].id
  port             = 8000
}
