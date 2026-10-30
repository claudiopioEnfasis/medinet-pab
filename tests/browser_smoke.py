"""Flujos React en copia aislada. Nunca ejecutar escrituras sobre la instalación.

python tests/browser_smoke.py --url http://127.0.0.1:3300 \
  --credentials-file <archivo privado JSON> --output <directorio privado> --allow-write
Requiere Playwright y Chromium; usuarios audit_browser_admin/viewer/coordinator.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


def verify(url, credentials_file, output):
    users = json.loads(Path(credentials_file).read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results, errors, console_errors = {}, [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="es-CL", timezone_id="America/Santiago")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        def login(role):
            page.goto(url)
            page.get_by_label("Usuario", exact=True).fill("audit_browser_" + role)
            page.get_by_label("Contraseña", exact=True).fill(users["audit_browser_" + role])
            with page.expect_response(lambda r: r.url.endswith("/api/auth/login") and r.request.method == "POST") as response:
                page.get_by_role("button", name="Entrar al sistema").click()
            assert response.value.status == 200
            token = response.value.json()["access_token"]
            page.locator(".room-card").first.wait_for()
            assert page.locator(".room-card").count() == 8
            results["login_" + role] = True
            return {"Authorization": "Bearer " + token}
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(url)
        assert page.locator(".auth-shell").evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length") == 1
        page.screenshot(path=str(output / "login-mobile.png"), full_page=True)
        results["mobile_login_single_column"] = True
        page.set_viewport_size({"width": 1440, "height": 1000})
        marker = "AUDITORIA-NAVEGADOR-V05-" + datetime.now(timezone.utc).strftime("%H%M%S")
        headers = login("admin")
        page.screenshot(path=str(output / "dashboard-desktop.png"), full_page=True)
        assert page.get_by_role("button", name="Agregar pabellón").is_visible()
        rooms = page.request.get(url + "/api/operating-rooms", headers=headers).json()
        patients = page.request.get(url + "/api/patients", headers=headers).json()
        staff = page.request.get(url + "/api/medical-staff", headers=headers).json()
        room = next(r for r in rooms if r["status"] == "available")
        page.get_by_role("button", name="Programar cirugía", exact=True).first.click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Pabellón").select_option(str(room["id"]))
        dialog.get_by_label("Paciente").select_option(str(patients[0]["id"]))
        dialog.get_by_label("Procedimiento", exact=True).fill(marker)
        dialog.locator(".staff-check").filter(has_text=staff[0]["full_name"]).get_by_role("checkbox").check()
        dialog.get_by_label("Inicio", exact=True).fill("2099-01-05T10:00")
        dialog.get_by_label("Término", exact=True).fill("2099-01-05T12:00")
        dialog.get_by_role("button", name="Verificar disponibilidad").click()
        dialog.get_by_text("Horario disponible", exact=True).wait_for()
        with page.expect_response(lambda r: r.url.endswith("/api/surgeries") and r.request.method == "POST") as response:
            dialog.get_by_role("button", name="Guardar cirugía").click()
        assert response.value.status == 201
        sid = response.value.json()["id"]
        page.get_by_role("dialog").wait_for(state="hidden")
        page.get_by_role("button", name="Programación", exact=True).first.click()
        row = page.locator(".surgery-row").filter(has_text=marker)
        row.wait_for()
        row.get_by_role("button", name="Iniciar", exact=True).click()
        row.get_by_role("button", name="Finalizar", exact=True).wait_for()
        row.get_by_role("button", name="Finalizar", exact=True).click()
        row.get_by_text("Finalizada", exact=True).wait_for()
        assert page.request.get(url + f"/api/surgeries/{sid}", headers=headers).json()["status"] == "completed"
        results["schedule_query_start_complete"] = True
        # Mensaje de error real ante una transición prohibida, sin tocar el original.
        page.get_by_role("button", name="Vista general", exact=True).first.click()
        page.locator(".room-card").filter(has_text=room["code"]).locator("select").select_option("available")
        card = page.locator(".room-card").filter(has_text="PAB-05")
        card.locator("select").select_option("available")
        page.get_by_role("alert").filter(has_text="cirugía en curso").wait_for()
        results["clear_conflict_message"] = True
        for width in (320, 390, 768):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Desbordamiento a {width}px"
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "dashboard-mobile.png"), full_page=True)
        results["mobile_no_horizontal_overflow"] = True
        page.get_by_role("button", name="Salir", exact=True).click()
        page.set_viewport_size({"width": 1440, "height": 1000})
        login("viewer")
        assert page.get_by_role("button", name="Programar cirugía", exact=True).count() == 0
        assert page.get_by_role("button", name="Agregar pabellón").count() == 0
        assert page.locator(".room-card select:enabled").count() == 0
        page.get_by_role("button", name="Salir", exact=True).click()
        login("coordinator")
        assert page.get_by_role("button", name="Programar cirugía", exact=True).first.is_visible()
        assert page.get_by_role("button", name="Agregar pabellón").count() == 0
        page.get_by_role("button", name="Salir", exact=True).click()
        page.goto(url + "/docs")
        page.locator(".swagger-ui .info .title").wait_for()
        servers = page.locator(".servers select").input_value()
        assert servers == "/api"
        assert page.request.get(url + servers + "/health/ready").status == 200
        page.screenshot(path=str(output / "swagger.png"), full_page=True)
        results["swagger_server_proxy"] = True
        results["page_errors"] = errors
        # Chromium registra el 409 deliberado como error de recurso HTTP.
        results["console_errors"] = console_errors
        assert not errors
        assert all("409" in message for message in console_errors)
        browser.close()
    (output / "browser-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--credentials-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-write", action="store_true")
    args = parser.parse_args()
    if not args.allow_write:
        parser.error("Usar exclusivamente una copia de pruebas y confirmar --allow-write")
    verify(args.url.rstrip("/"), args.credentials_file, args.output)
