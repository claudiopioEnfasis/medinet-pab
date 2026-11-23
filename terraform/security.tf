# Security Groups encadenados por capa:
#   Internet -> ALB -> EC2 (web/api) -> RDS
# Ningún salto se puede omitir: no existe ingreso directo a EC2 ni a RDS.

# ---------------------------------------------------------------------------
# ALB: único punto de entrada público
# ---------------------------------------------------------------------------
# El ALB es el unico punto de entrada publico de la arquitectura (requisito de
# la pauta EVA 03): 80/443 deben aceptar Internet. El trafico hacia las capas
# internas queda restringido por los SG de aplicacion y de base de datos.
# Justificacion y referencia: docs/EVA03_PLAN.md seccion 4.
#tfsec:ignore:AVD-AWS-0107
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "Ingreso publico 80/443 al Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  # 80 solo para redirigir a 443.
  #checkov:skip=CKV_AWS_260:El puerto 80 es el punto de entrada publico obligatorio y responde 301 hacia HTTPS; Justificacion: docs/EVA03_PLAN.md seccion 4.
  ingress {
    description = "HTTP publico (redirige a HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_web_cidrs
  }

  ingress {
    description = "HTTPS publico (FQDN con certificado ACM)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_web_cidrs
  }

  # La salida hacia los nodos se declara como regla independiente
  # (aws_vpc_security_group_egress_rule) para no crear un ciclo de dependencias:
  # el SG de aplicacion ya referencia a este SG en sus ingresos.
  tags = { Name = "${local.name_prefix}-sg-alb", Tier = "edge" }
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app_web" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Solo el frontend de los nodos, sin rangos abiertos"
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  referenced_security_group_id = aws_security_group.app.id
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app_api" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Solo el backend de los nodos, sin rangos abiertos"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.app.id
}

# ---------------------------------------------------------------------------
# Nodos EC2: solo aceptan tráfico del SG del ALB
# ---------------------------------------------------------------------------
# Salida a Internet imprescindible para el arranque (apt, git clone y pull de
# imagenes desde GHCR) a traves del NAT. No hay ingreso publico: las unicas
# reglas de entrada vienen del SG del ALB, por lo que el egress abierto no
# expone superficie de ataque.
# Justificacion y referencia: docs/EVA03_PLAN.md seccion 4.
#tfsec:ignore:AVD-AWS-0104
resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app"
  description = "Nodos EC2: web 8080 y api 8000 solo desde el SG del ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Frontend Nginx solo desde el ALB"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Backend FastAPI solo desde el ALB (health checks y /health)"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Egress de minimo privilegio: solo lo que necesita el arranque del nodo
  # (apt/git/GHCR por 80 y 443 via NAT, DNS y PostgreSQL dentro de la VPC).
  # El acceso a Internet es de salida unicamente: no hay ingreso publico.
  egress {
    description = "HTTPS de salida (apt, git clone, GHCR)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP de salida solo para repositorios apt de Ubuntu"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "DNS del resolver de la VPC"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "PostgreSQL solo dentro del CIDR privado de la VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = { Name = "${local.name_prefix}-sg-app", Tier = "app" }
}

# ---------------------------------------------------------------------------
# RDS: solo acepta el puerto del motor desde el SG de los nodos
# ---------------------------------------------------------------------------
resource "aws_security_group" "db" {
  name        = "${local.name_prefix}-db"
  description = "PostgreSQL 5432 solo desde los nodos de backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL desde el SG de los nodos de aplicacion"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  # Sin bloques egress: RDS solo responde. La regla de salida por defecto del
  # SG no se usa porque el tráfico de respuesta lo maneja el stateful firewall.
  #checkov:skip=CKV_AWS_382:Security Group stateful; RDS no inicia conexiones salientes; Justificacion: docs/EVA03_PLAN.md seccion 4.

  tags = { Name = "${local.name_prefix}-sg-db", Tier = "data" }
}
