# Seguridad v0.5: resultados locales

> Documento de una revisión anterior. Para el estado de esta entrega, consultar
> [AUDITORIA_INTEGRAL_V05.md](AUDITORIA_INTEGRAL_V05.md) y
> [ENTREGA_TECNICA_V05.md](ENTREGA_TECNICA_V05.md). Los resultados históricos no
> acreditan la aplicación de los cambios nuevos a la instalación original.


**Revisión posterior:** los hallazgos de dependencias e imágenes descritos aquí
fueron corregidos. Consulta [REVISION_FINAL_V05.md](REVISION_FINAL_V05.md) para
los nuevos escaneos y los pendientes de configuración. Este archivo conserva
la evidencia inicial.

Fecha: 30 de octubre de 2026. Estos escaneos tienen hallazgos abiertos; el pipeline de seguridad no está aprobado para AWS.

| Control | Resultado |
|---|---|
| Bandit sobre app y scripts | Aprobado, sin hallazgos |
| npm audit de dependencias de producción del lockfile | Aprobado, cero vulnerabilidades |
| pip-audit del conjunto instalado en la imagen API | 37 entradas de avisos en tres paquetes; incluye pip del runtime |
| Trivy api, filtro del workflow | 8 HIGH y 1 CRITICAL |
| Trivy web, filtro del workflow | 46 HIGH y 1 CRITICAL |

Trivy se ejecutó con `--scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`, equivalente al filtro del workflow. Ambos escaneos devolvieron código 1. Las entradas no son necesariamente CVE distintas: una vulnerabilidad puede afectar varios paquetes y los avisos pip pueden tener aliases/duplicados. `ignore-unfixed` omite otros hallazgos sin corrección; este informe no afirma ausencia de estos.

El primer intento de `pip-audit -r requirements.txt` no pudo crear su entorno temporal porque el host carece de ensurepip. Se auditó en cambio el inventario exacto de dependencias instaladas en la imagen API, con versiones fijadas, `--no-deps --disable-pip`. Ese inventario incluye la herramienta pip, que no es una dependencia declarada de la aplicación.

## Paquetes señalados por Trivy

| Imagen | Paquete | Versión instalada | Versión de corrección informada |
|---|---|---|---|
| api | PyJWT | 2.13.0 | 2.14.0 |
| api | starlette | 0.50.0 | 1.1.0 |
| api | starlette | 0.50.0 | 1.3.1 |
| web | brotli-libs | 1.2.0-r0 | 1.2.1-r0 |
| web | c-ares | 1.34.6-r0 | 1.34.8-r0 |
| web | curl | 8.17.0-r1 | 8.20.0-r0 |
| web | curl | 8.17.0-r1 | 8.22.0-r0 |
| web | curl | 8.17.0-r1 | 8.23.0-r0 |
| web | libcrypto3 | 3.5.6-r0 | 3.5.7-r0 |
| web | libcrypto3 | 3.5.6-r0 | 3.5.8-r0 |
| web | libcurl | 8.17.0-r1 | 8.20.0-r0 |
| web | libcurl | 8.17.0-r1 | 8.22.0-r0 |
| web | libcurl | 8.17.0-r1 | 8.23.0-r0 |
| web | libexpat | 2.7.5-r0 | 2.8.1-r0 |
| web | libexpat | 2.7.5-r0 | 2.8.4-r0 |
| web | libexpat | 2.7.5-r0 | 2.8.5-r0 |
| web | libexpat | 2.7.5-r0 | 2.9.0-r0 |
| web | libssl3 | 3.5.6-r0 | 3.5.7-r0 |
| web | libssl3 | 3.5.6-r0 | 3.5.8-r0 |
| web | libuuid | 2.41.4-r0 | 2.41.6-r0 |
| web | libuuid | 2.41.4-r0 | 2.41.6-r1 |
| web | libxml2 | 2.13.9-r0 | 2.13.9-r1 |
| web | pcre2 | 10.47-r0 | 10.48-r0 |
| web | pcre2 | 10.47-r0 | 10.49-r0 |
| web | tiff | 4.7.1-r0 | 4.7.2-r0 |

El detalle de IDs, aliases, severidad y fuentes está en [seguridad-v05.json](evidencias/seguridad-v05.json). Las credenciales y los tokens no forman parte de estos archivos.

Antes de AWS se deben actualizar las dependencias afectadas (PyJWT y Starlette, revisando su compatibilidad con FastAPI), la herramienta pip y las bibliotecas del sistema de la imagen web. Después corresponde reconstruir, repetir regresión funcional y volver a ejecutar los escaneos. No se añadieron exclusiones ni se redujeron umbrales para aprobar artificialmente el pipeline. No se hizo una migración de dependencias mayores en esta tarea de datos de demostración.
