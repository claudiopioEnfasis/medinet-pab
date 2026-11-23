"""Verificacion estatica del criterio 1 (EVA 03) sobre terraform/.

No necesita credenciales de AWS ni estado: lee los .tf y comprueba que cada
elemento exigido por la pauta exista y tenga la configuracion esperada.

Uso:  python scripts/verificar_criterio1_tf.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "terraform"
SRC = {p.name: p.read_text(encoding="utf-8") for p in sorted(ROOT.glob("*.tf"))}
ALL = "\n".join(SRC.values())


def block(kind, name):
    """Devuelve el cuerpo del bloque resource del tipo y nombre indicados."""
    pattern = rf'resource\s+"{re.escape(kind)}"\s+"{re.escape(name)}"\s*\{{(.*?)\n\}}'
    match = re.search(pattern, ALL, re.S)
    return match.group(1) if match else ""


def variable(name):
    pattern = rf'variable\s+"{re.escape(name)}"\s*\{{(.*?)\n\}}'
    match = re.search(pattern, ALL, re.S)
    return match.group(1) if match else ""


results = []


def check(label, condition, detail=""):
    results.append(condition)
    print(f"[{'OK' if condition else 'FALLA'}] {label}" + (f"  ({detail})" if detail else ""))


vpc = block("aws_vpc", "main")
subnet_public = block("aws_subnet", "public")
subnet_private = block("aws_subnet", "private")
sg_app = block("aws_security_group", "app")
sg_db = block("aws_security_group", "db")
alb = block("aws_lb", "main")
tg_frontend = block("aws_lb_target_group", "frontend")
tg_backend = block("aws_lb_target_group", "backend")
listener_https = block("aws_lb_listener", "https")
listener_http = block("aws_lb_listener", "http_redirect")
instance = block("aws_instance", "app")
rds = block("aws_db_instance", "main")

check("VPC con DNS support y hostnames",
      "enable_dns_support   = true" in vpc
      and "enable_dns_hostnames = true" in vpc)

check("2 subredes publicas (una por AZ)",
      "count = var.availability_zone_count" in subnet_public
      and len(re.findall(r'"10\.20\.1[01]\.0/24"', variable("public_subnet_cidrs"))) == 2,
      "availability_zone_count por defecto 2")

check("2 subredes privadas (una por AZ)",
      "count = var.availability_zone_count" in subnet_private
      and len(re.findall(r'"10\.20\.2[01]\.0/24"', variable("private_subnet_cidrs"))) == 2,
      "availability_zone_count por defecto 2")

check("Internet Gateway y ruta publica 0.0.0.0/0",
      "gateway_id = aws_internet_gateway.main.id" in ALL
      and "allocation_id = aws_eip.nat.id" not in vpc)

check("NAT Gateway con EIP y ruta privada por defecto",
      "allocation_id = aws_eip.nat.id" in ALL
      and "nat_gateway_id = aws_nat_gateway.main.id" in ALL)

check("SG encadenados ALB -> APP -> DB",
      "security_groups = [aws_security_group.alb.id]" in sg_app
      and "from_port       = 8080" in sg_app
      and "security_groups = [aws_security_group.app.id]" in sg_db
      and "from_port       = 5432" in sg_db)

check("ALB publico en las subredes publicas",
      "internal           = false" in alb
      and "subnets            = aws_subnet.public[*].id" in alb
      and "security_groups    = [aws_security_group.alb.id]" in alb)

check("2 target groups con health checks",
      len(re.findall(r'resource\s+"aws_lb_target_group"', ALL)) == 2
      and "health_check {" in tg_frontend
      and "health_check {" in tg_backend
      and "path                = local.backend_health_path" in tg_backend)

check("listener 443 HTTPS con certificado ACM",
      "port              = 443" in listener_https
      and 'protocol          = "HTTPS"' in listener_https
      and "certificate_arn   = var.certificate_arn" in listener_https)

check("listener 80 redirige a 443 con HTTP_301",
      "port              = 80" in listener_http
      and 'type = "redirect"' in listener_http
      and 'port        = "443"' in listener_http
      and 'status_code = "HTTP_301"' in listener_http)

check("2 EC2 sin IP publica en subredes privadas",
      "count = var.instance_count" in instance
      and "associate_public_ip_address = false" in instance
      and "aws_subnet.private[count.index % var.availability_zone_count].id" in instance
      and "condition     = var.instance_count >= 2" in variable("instance_count"))

check("RDS Multi-AZ, cifrada y no publica",
      "multi_az               = var.db_multi_az" in rds
      and "storage_encrypted     = true" in rds
      and "publicly_accessible    = false" in rds
      and "default     = true" in variable("db_multi_az"))

print(f"\n{sum(results)}/{len(results)} verificaciones correctas")
sys.exit(0 if all(results) else 1)
