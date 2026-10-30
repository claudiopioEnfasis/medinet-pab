"""Controles CI reproducibles: credenciales desechables, JUnit y política Trivy."""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

CRITICAL_TESTS = {
    "test_postgres_parallel_reservations", "test_parallel_reservations_each_resource",
    "test_parallel_start_shared_resource", "test_parallel_status_same_surgery",
    "test_parallel_failed_logins_cannot_bypass_lock", "test_migrations_and_runtime_least_privilege",
    "test_seed_complete_demo_and_four_states",
}


def prepare_env(output, port=5432):
    password, jwt_secret = secrets.token_hex(32), secrets.token_hex(32)
    values = dict(POSTGRES_USER="ci_user", POSTGRES_PASSWORD=password, POSTGRES_DB="medinet_ci",
                  JWT_SECRET=jwt_secret,
                  TEST_DATABASE_URL=f"postgresql+psycopg://ci_user:{password}@127.0.0.1:{port}/medinet_ci")
    if os.getenv("GITHUB_ACTIONS") == "true":
        for value in (password, jwt_secret, values["TEST_DATABASE_URL"]):
            print("::add-mask::" + value)
    with Path(output).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")
    Path(output).chmod(0o600)
    print("Variables CI desechables generadas; no se leyó .env")


def validate_db():
    value = os.getenv("TEST_DATABASE_URL", "")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "postgresql+psycopg" and parsed.hostname in {"localhost", "127.0.0.1"}
                 and parsed.path == "/medinet_ci" and parsed.username == "ci_user" and bool(parsed.password))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("CI exige PostgreSQL desechable medinet_ci en loopback; conexión ausente o no admitida")
    print("Destino PostgreSQL exclusivo de CI validado")


def verify_tests(filename):
    from defusedxml import ElementTree
    path = Path(filename)
    content = path.read_text()
    for value in sorted((os.getenv(key, "") for key in ("TEST_DATABASE_URL", "POSTGRES_PASSWORD", "JWT_SECRET")), key=len, reverse=True):
        if value:
            content = content.replace(value, "[REDACTED]")
    path.write_text(content)
    root = ElementTree.fromstring(content)
    cases = list(root.iter("testcase"))
    names = {case.attrib.get("name", "").split("[", 1)[0] for case in cases}
    missing = CRITICAL_TESTS - names
    skipped = len(list(root.iter("skipped")))
    failed = len(list(root.iter("failure"))) + len(list(root.iter("error")))
    print(f"JUnit: {len(cases)} casos; {skipped} omitidos; {failed} fallos/errores")
    if not cases or missing or skipped or failed:
        raise ValueError("Suite CI incompleta o fallida; faltantes críticos: " + ", ".join(sorted(missing)))


def verify_trivy(filenames):
    blocked = False
    for filename in filenames:
        data = json.loads(Path(filename).read_text())
        if data.get("SchemaVersion") != 2 or not isinstance(data.get("Results"), list):
            raise ValueError("Reporte Trivy ausente o inválido")
        counts = {}
        for result in data["Results"]:
            for finding in result.get("Vulnerabilities", []):
                severity = finding["Severity"]
                counts[severity] = counts.get(severity, 0) + 1
                if severity in {"HIGH", "CRITICAL"}:
                    blocked = True
                    print(f"BLOQUEO {severity}: {finding['VulnerabilityID']} / {finding['PkgName']} / corrección: {finding.get('FixedVersion', 'no disponible')}")
        print(f"Trivy {Path(filename).name}: {json.dumps(counts, sort_keys=True)}")
    if blocked:
        raise ValueError("Política Trivy: HIGH/CRITICAL bloquean, también sin corrección")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-env")
    prepare.add_argument("output")
    prepare.add_argument("--port", type=int, default=5432)
    commands.add_parser("validate-db")
    commands.add_parser("tests").add_argument("report")
    commands.add_parser("trivy").add_argument("reports", nargs="+")
    args = parser.parse_args()
    if args.command == "prepare-env":
        prepare_env(args.output, args.port)
    elif args.command == "validate-db":
        validate_db()
    elif args.command == "tests":
        verify_tests(args.report)
    else:
        verify_trivy(args.reports)


if __name__ == "__main__":
    main()
