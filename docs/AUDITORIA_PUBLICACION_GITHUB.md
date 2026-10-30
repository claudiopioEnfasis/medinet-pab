# Auditoría de seguridad antes de publicar MediNet PAB

Fecha: 30-10-2026. Repositorio: https://github.com/claudiopioEnfasis/medinet-pab.
Base de la auditoría inicial: `5e45c59da77e38a7c551cbe24a90072293b2475b` más los cambios locales
indicados aquí. El repositorio permanece **privado**. No se hizo push, no se
reescribió historial, no se modificaron credenciales ni se realizaron cambios AWS.

**Actualización final GHCR:** commit `c7a98b40ecbba2f23aaf5c1ef8c37ef039a4b1be`.
La sección 10 actualiza cobertura, digests y conclusión; las secciones anteriores
conservan los resultados y alcance de la auditoría inicial.

## 1. Alcance y límites

Se revisaron archivos versionados y nuevos publicables, nombres de archivos
sensibles en cada snapshot, historial alcanzable por todas las referencias
locales, reflogs, referencias anunciadas por GitHub, documentación, capturas,
workflows, configuración Actions, logs y artefactos disponibles de sus ejecuciones.
Se compararon los secretos locales conocidos con el contenido histórico sin
imprimir sus valores. Los archivos privados se leyeron exclusivamente para
verificación: no se modificaron ni copiaron al informe.

**Límite inicial y actualización:** la API de inventario GHCR devolvió HTTP 403
por ausencia de alcance `read:packages`. El propietario posteriormente confirmó
las nueve versiones y se completó la inspección de sus nueve artefactos (sección
10). Sigue pendiente comprobar los digests actuales de esos tags y su visibilidad
efectiva mediante lectura independiente del registro.
No se pidieron tokens adicionales ni se modificaron permisos de cuenta.
No se inspeccionaron recursos reales AWS ni copias externas del repositorio.
La auditoría identifica exposición de secretos; no demuestra su ausencia absoluta.

## 2. Herramientas y método reproducible

- Git: fetch autenticado mediante helper de gh, ls-remote, for-each-ref, rev-list,
  ls-tree, cat-file y fsck; sin checkout de otra rama ni escritura remota.
- Gitleaks **8.30.1**, imagen
  `zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.
- Revisión de cada blob histórico completo, además del escaneo de diffs de Git.
- Comparación exacta con JWT, contraseñas y URL restringida existentes, con revisión
  contextual para no confundir coincidencias cortas con credenciales incrustadas.
- GitHub CLI/API autenticados en modo lectura para referencias, ejecuciones,
  permisos, nombres de Secrets/Variables/Environments y metadatos de paquetes.
- Verificación SHA-256 del artefacto Docker y lectura estática de configuración,
  historial y archivos regulares de sus capas, incluidas capas posteriormente
  eliminadas. Los archivos mayores a 5 MB y enlaces no se escanearon como texto;
  se inventariaron sus nombres. No es análisis forense de binarios. Sin ejecutar
  código de las imágenes remotas ni iniciar bases nuevas.
- Actionlint fijado por digest y 16 pruebas de gates/entrega; revisión visual de
  las ocho capturas PNG versionadas. No se detectaron pacientes reales en ellas.

Comandos base, desde el repositorio (crear un directorio privado ignorado para
reportes; nunca publicar resultados sin revisar):

```bash
umask 077
mkdir -p backups/publication-audit
chmod 700 backups/publication-audit
git -c credential.helper='!gh auth git-credential' fetch --all --tags --prune
git -c credential.helper='!gh auth git-credential' ls-remote origin
git rev-list --all --reflog --count
git fsck --full --no-reflogs --unreachable

docker run --rm -v "$PWD:/repo:ro" \
  -v "$PWD/backups/publication-audit:/out" \
  zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f \
  git /repo --log-opts='--all --full-history' --redact=100 \
  --report-format json --report-path /out/history-repeat.json
```

Para archivos actuales, escanear una copia formada por `git ls-files --cached
--others --exclude-standard`, sin incluir los privados ignorados. En CI no existe
el .env local y se escanea directamente el checkout. La configuración predeterminada
de Gitleaks se mantiene: no se agregaron allowlists para ocultar hallazgos.
El detector se comprobó con un token **sintético sin validez**: lo detectó y devolvió
código 1. Las alertas ambiguas de esta auditoría se clasificaron manualmente.

Los reportes completos quedan en backups/publication-audit, ignorado por Git y
Docker y protegido con permisos privados. El [resumen publicable](evidencias/auditoria-publicacion-github.json)
contiene únicamente metadatos y resultados, sin secretos ni hashes de contraseñas.

## 3. Ramas e historial revisados

La consulta remota autenticada anunció solamente HEAD y `refs/heads/main`, ambos
apuntando a `5e45c59da77e38a7c551cbe24a90072293b2475b`. API de ramas: una rama;
API de tags y Pull Requests: listas vacías. Fetch no superficial, completo para
las referencias anunciadas; ningún tag ni referencia PR pendiente de descargar.

Historial remoto/main: **3 commits**:

| Commit | Descripción |
|---|---|
| `a1d0b4ca08360b9acafda87eb860e61b3fe023a1` | v0,5 inicial |
| `add85a09a03fd0fa9f5410ea4e252e09540b3f67` | Auditoría, mínimo privilegio y entrega técnica |
| `5e45c59da77e38a7c551cbe24a90072293b2475b` | Implementación CI/CD y preparación AWS |

Además se revisaron referencias locales `refs/agents/.../checkpoints/...` y
`refs/codex/turn-diffs/checkpoints/...`: **14 commits en total**, también al incluir
reflogs, con **138 blobs únicos**. fsck no informó objetos inalcanzables. No se
publicaron ni borraron checkpoints. Gitleaks informó 8 commits con contenido de
diff escaneable; eso no equivale a reducir el alcance a 8: se exportaron y
escanearon separadamente los 138 blobs completos de los 14 snapshots alcanzables.

No se encontraron versiones históricas de .env con credenciales, claves privadas,
dumps SQL, respaldos ni bases SQLite. No se detectaron tokens GitHub/AWS, JWT
privados o contraseñas reales incrustados en esos blobs. No se pueden enumerar
referencias remotas ya borradas, cachés internos de GitHub ni clones de terceros;
la cobertura remota se refiere a todas las referencias actualmente anunciadas.

## 4. Hallazgos por gravedad

| ID | Gravedad | Hallazgo y estado |
|---|---|---|
| C-01 | Crítico | **Ningún secreto real expuesto confirmado** en el material revisado. Esto no elimina los límites de alcance. |
| A-01 | Alto / alcance incompleto | Inventario y visibilidad de GHCR no verificables con la autorización disponible (403). Las imágenes de Actions revisadas no certifican versiones adicionales del registro. **Pendiente antes de una aprobación integral.** |
| A-02 | Alto si se activa CD sin controles | No hay Environment production ni protección efectiva comprobada de main; la protección privada devolvió 403 por plan. **Mitigado actualmente:** no hay Secrets, ambas variables de activación están ausentes y CD está omitido. Mantenerlo así hasta autorización y protección verificadas. |
| M-01 | Medio | Faltaban exclusiones de claves sin extensión, dumps .sql, variantes *.env, credenciales de herramientas y logs; el contexto Docker del frontend tenía menos protecciones. **Corregido localmente**, sin borrar archivos. |
| M-02 | Medio | No existía un gate específico de secretos. **Corregido localmente:** Gitleaks de historial con fetch-depth:0 y árbol actual, redacción total y bloqueo antes de publicar imágenes. Pendiente ejecución remota de este cambio. |
| M-03 | Medio | Credencial administrativa PostgreSQL local de baja fortaleza, ya documentada, sin exposición demostrada en Git. No se cambió. Requiere plan y respaldo antes de rotar y antes de usarla en una instancia accesible; no reutilizarla en EC2. |
| M-04 | Medio | Al publicar, historial/logs Actions y artefactos pasan a ser superficie pública; se revisó el material disponible. Mantener política de no imprimir entorno, tokens, dumps o datos reales. |
| M-05 | Medio | Configuración remota permite todas las acciones y no exige SHA globalmente. Los workflows actuales sí fijan sus acciones por SHA y usan permisos mínimos. Evaluar política remota de acciones permitidas y SHA sin alterar su configuración en esta auditoría. |
| B-01 | Bajo | Metadatos Git incluyen identidad/correo de autor; rutas locales y nombres de cuenta aparecen en documentación/logs. No son claves ni datos clínicos. Confirmar consentimiento de autores antes de publicación; no se reescribió metadata. |
| B-02 | Bajo | Mantener actualización de detectores y revisión humana de capturas, fixtures y futuras contribuciones. Un resultado cero del detector no prueba que todo contenido sea publicable. |

### Alertas investigadas y descartadas

- Coincidencia con contraseña local en scripts/create_user.py, línea 22, presente
  desde `a1d0b4c...` y en snapshots posteriores: es una **subcadena de la lista de
  caracteres permitidos para un nombre de usuario**, no una asignación de
  contraseña ni una URL. No se cambió la validación ni se reprodujo el valor.
- Gitleaks marcó `generic-api-key` en el artefacto image-security-results
  `13006410175`, reporte API, líneas 71 y 206, y en dos campos del config Docker
  de cada uno de los dos artefactos de publicación: `GPG_KEY` es la **huella pública de verificación de Python**, que
  también figura en el Dockerfile oficial. No es material privado ni un token.
  La explicación no añade ninguna supresión al CI.
- En capas base se identificó cacert.pem del paquete certifi: almacén de
  certificados públicos, no clave privada SSH/TLS de la aplicación.
- Fixtures de pruebas contienen claves/contraseñas sintéticas de test y esquemas
  de CI; no coinciden con JWT/contraseña restringida reales. El .env.example deja
  los secretos vacíos. No se encontraron credenciales operativas en documentación.

Referencia de la huella pública: [Dockerfile oficial Python](https://github.com/docker-library/python/blob/master/3.12/alpine3.23/Dockerfile).

## 5. Resultados de archivos, datos y artefactos

| Revisión | Resultado |
|---|---|
| Gitleaks historial Git y copia de blobs completos | 0 alertas |
| Gitleaks archivos actuales publicables | 0 alertas |
| Nombres sensibles en todos los snapshots | Ningún .env privado, clave privada, dump o base versionados |
| Comparación con secretos locales | Sin exposición confirmada; coincidencia corta contextual descartada |
| Capturas/documentación | Datos marcados FICTICIO/DEMOSTRACIÓN; usuarios de validación; sin passwords, JWT o historias clínicas reales visibles |
| Logs remotos | Descargados todos los 4 runs listados; el run CD omitido no contiene logs; sin secretos reales confirmados |
| Artefactos de seguridad y JUnit | Descargados los 3 disponibles; dos alertas por huella pública explicadas arriba |
| Imágenes de los dos artefactos de publicación disponibles | SHA-256 correcto en ambos; seis imágenes API/web/DB inspeccionadas estáticamente por capas y configuración; sin .env o claves operativas identificadas |
| GHCR completo | **No verificado**: inventario API 403; no se afirma ausencia de secretos en todos sus tags |
| Contextos Docker raíz y frontend | Verificación BuildKit de contexto sin .env privado, claves identificadas, .git ni backups; sin copiar contexto a una imagen |
| Actionlint / git diff --check | Aprobados con cambios locales |
| Tests pertinentes | 16 aprobados; warning existente de deprecación HTTPX/TestClient, no ocultado |

La revisión visual y del seed respalda que el material publicado es ficticio; no
certifica la procedencia de todos los registros de una base privada. No se volcó
la base local ni se copiaron sus filas al repositorio. Los backups contienen datos
y hashes de roles, aun siendo de laboratorio: deben seguir privados y cifrados.

## 6. GitHub Actions y recepción de PR externos

Workflows revisados: [CI](../.github/workflows/ci-cd.yml) y
[CD EC2](../.github/workflows/deploy-ec2.yml), además de sus versiones históricas.

- Token por defecto contents:read; escritura packages limitada a publicación main;
  lectura packages limitada a entrega. Configuración remota confirma token por
  defecto read y sin permiso para aprobar PR.
- pull_request ejecuta tests/build con runner hospedado efímero; sin Secrets de
  producción. No hay pull_request_target ni runner self-hosted. Checkout no
  persiste credenciales. No autorizar secretos/write tokens para PR de forks.
- Publicación exige push main y todos los gates. Un PR no publica en nuestro GHCR.
- workflow_run puede tener acceso privilegiado en GitHub: aquí se exige éxito,
  origen push main del mismo repositorio y SHA actual con CI exitoso. No ejecuta
  scripts ni artefactos descargados de PR. El destino usa Environment production,
  SSH con host key fija y comando forzado; las claves privadas solo deben existir
  como Secrets del Environment cuando se autorice su preparación.
- La consulta actual devolvió **0 Secrets, 0 Variables y 0 Environments**. La API
  de alertas de secretos devolvió 404 indicando que Secret scanning está
  deshabilitado: no equivale a una lista de alertas vacía. No hay
  ENABLE_EC2_DEPLOY ni EC2_SECURITY_REVIEWED: CD queda cerrado. Publicar el repo
  no agrega estas variables ni constituye autorización de despliegue.
- La consulta de aprobación de contribuciones de forks respondió 422 porque el
  repositorio aún es privado. Cuando se autorice su publicación, configurar
  aprobación de workflows de **todos los colaboradores externos**, revisar cambios
  de YAML/scripts antes de aprobar y no exponer Secrets del entorno de producción.
- Tras hacerse público pueden estar disponibles reglas de main y revisores de
  Environments según el plan. Configurarlos efectivamente: exigir PR/revisión,
  checks, main como rama permitida, impedir autoaprobación y limitar bypass. No
  asumir que el nombre production o main impone por sí solo estas restricciones.

Evidencia remota de la auditoría inicial (actualización posterior en sección 10):

- [CI 41114841130](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41114841130):
  éxito en `5e45c59...`; Test PostgreSQL, Python/YAML, React/npm, Docker/Trivy y
  publicación GHCR exitosos.
- [CD 41115368500](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41115368500):
  **skipped**, mismo SHA; no acredita despliegue.
- Se revisaron también los runs 41089671930 y 41022533818 y sus logs disponibles.
- El gate Gitleaks no estaba ejecutado remotamente al cerrar la auditoría inicial.
  La continuación verificó que sí aprobó en el run 41133919857; ver sección 10.

## 7. Efectos de hacer público GitHub/GHCR/documentación

GitHub documenta que el código, historial Actions y logs se hacen visibles y
cualquiera puede crear un fork. No confiar en volver a privado para retirar
información que terceros ya hayan copiado. Revisar artefactos y logs antiguos,
no solamente el árbol de archivos actual.
[Fuente oficial](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).

GHCR tiene controles granulares: la visibilidad del paquete no debe deducirse de
la visibilidad del repositorio. Paquetes enlazados pueden heredar accesos, pero no
necesariamente visibilidad; los contenedores públicos permiten pulls anónimos.
Matías debe comprobar visibilidad, vínculo al repo, acceso Actions, tags/digests
y cada versión retenida antes de publicarla. No incluir .env, claves, dumps ni
secretos mediante COPY, ARG, ENV o pasos RUN, tampoco en capas eliminadas después.
[Fuente oficial](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

Publicar permite protecciones de Environment disponibles en repositorios públicos
en planes actuales. Aun así deben configurarse y comprobarse; no se activaron en
esta sesión. Mantener EC2 apagado/desconectado del CD hasta autorización explícita.
[Fuente oficial](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

## 8. Archivos modificados y controles de conservación

- [.gitignore](../.gitignore), [.dockerignore](../.dockerignore) y
  [frontend/.dockerignore](../frontend/.dockerignore): exclusiones adicionales
  de secretos, backups, logs y credenciales de herramientas. No eliminan archivos
  existentes ni retiran archivos ya versionados del historial.
- [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml): job Gitleaks fijado
  por digest, historial completo disponible y árbol actual, redacción total y
  dependencia obligatoria antes de construir/publicar imágenes.
- [Este informe](AUDITORIA_PUBLICACION_GITHUB.md),
  [evidencia resumida](evidencias/auditoria-publicacion-github.json) y
  [guía CI/CD](GITHUB_ACTIONS_CICD.md): alcance, resultados y referencia al gate.

No se modificó código funcional, archivo .env, archivo .env.runtime, credencial
real, volumen, registro de datos ni recursos AWS. No se hizo commit/push, ni se
cambió la visibilidad del repo o de paquetes.

## 9. Si se detecta un secreto posteriormente

No se confirmó ninguno que obligue ahora a reescribir historial. Si aparece uno:

1. Conservar evidencia privada mínima: archivo, commit, tipo y alcance, sin valor.
2. Revocar token GitHub/PAT o credencial AWS en su proveedor; rotar JWT (invalida
   sesiones) y contraseñas DB mediante ventana, respaldo/restauración verificados
   y prueba de acceso restringido. Clave SSH: reemplazar authorized_keys y actualizar
   Secrets por procedimiento revisado. Nada de esto se ejecutó aquí.
3. Retirar el secreto del árbol actual y de los artefactos/imágenes afectados. Un
   commit que borra el archivo no limpia el historial ni las capas Docker.
4. **Solo con autorización explícita adicional:** plan de git-filter-repo sobre
   copia de mantenimiento, inventario de refs, respaldo privado, coordinación con
   Matías, validación de todos los refs y publicación reescrita controlada. No dar
   instrucciones de force push como paso autorizado en esta auditoría.
5. Considerar PR refs/cachés y soporte GitHub para retirada de datos sensibles;
   renovar clones y repetir detectores. Limpiar historial no vuelve válido un
   secreto ya divulgado: revocación/rotación sigue siendo obligatoria.

## 10. Auditoría final GHCR: nueve imágenes

### Inventario y cobertura efectiva

El propietario confirmó en GitHub, en esta conversación, exactamente tres versiones
etiquetadas por paquete y ninguna sin etiqueta. Esta confirmación **cierra el
inventario visual declarado**; no se atribuye a una consulta automática ni a una
captura inspeccionada por este agente. No se utiliza como prueba de ausencia de
secretos. Las nueve combinaciones son:

| Paquete | Tag SHA (prefijo) | Contenido inspeccionado | Fuente verificable |
|---|---|---|---|
| medinet-pab-db | `c7a98b40…` | Sí, artefacto; config y todas las capas | [run 41133919857](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41133919857) |
| medinet-pab-api | `c7a98b40…` | Sí, artefacto; config y todas las capas | [run 41133919857](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41133919857) |
| medinet-pab-web | `c7a98b40…` | Sí, artefacto; config y todas las capas | [run 41133919857](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41133919857) |
| medinet-pab-api | `5e45c59d…` | Sí, artefacto; config y todas las capas | [run 41114841130](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41114841130) |
| medinet-pab-web | `5e45c59d…` | Sí, artefacto; config y todas las capas | [run 41114841130](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41114841130) |
| medinet-pab-db | `5e45c59d…` | Sí, artefacto; config y todas las capas | [run 41114841130](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41114841130) |
| medinet-pab-api | `add85a09…` | Sí, artefacto; config y todas las capas | [run 41089671930](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41089671930) |
| medinet-pab-web | `add85a09…` | Sí, artefacto; config y todas las capas | [run 41089671930](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41089671930) |
| medinet-pab-db | `add85a09…` | Sí, artefacto; config y todas las capas | [run 41089671930](https://github.com/claudiopioEnfasis/medinet-pab/actions/runs/41089671930) |

**Cobertura: 9/9 contenidos inspeccionados mediante artefactos; 0/9 únicamente
existencia. Resolución directa de los tags actuales de GHCR: 0/9 verificada.**
Esto distingue el contenido publicado en esos runs del contenido que el registro
pueda servir hoy bajo un tag mutable.

El run **41133919857** de c7a98b40… terminó en success: tests, Gitleaks, build,
seguridad y publicación. Se descargó su artefacto scanned-images **13014596958**
y logs. El CD **41134382990** quedó skipped; no se ejecutó despliegue. Los otros
dos bundles se conservaron de los runs 41114841130 y 41089671930.

### Integridad, correspondencia y significado de los digests

1. Se calculó SHA-256 de cada uno de los tres archivos medinet-images.tar.gz y
   se comparó con su checksum del artefacto: correctos.
2. Se verificaron hashes de manifests OCI, config JSON y blobs de capas del
   archivo, y los diff_ids de las capas descomprimidas contra rootfs.diff_ids:
   **111 referencias de capa verificadas, 64 capas únicas extraídas**.
3. Se revisó el workflow de ese commit: el job de publicación descarga el mismo
   artefacto, verifica checksum, hace docker load y tag/push sin reconstruir.
   Los logs nombran el repositorio de cada push y su digest. Es evidencia de
   procedencia de publicación, no lectura independiente del estado actual de GHCR.
4. No confundir digest de config (identidad/config de imagen), digest del manifest
   OCI exportado y digest de manifest comunicado por GHCR al hacer push. Son
   objetos diferentes; el transporte puede cambiar compresión/formato y su hash.
   No se presenta una diferencia entre ellos como fuga o corrupción, ni se afirma
   que los digests de publicación se recalcularon desde el servidor.

Los hashes completos del artefacto, config y manifest OCI verificados figuran por
imagen en el JSON de evidencia. Para contrastar desde GitHub, estos son los
**digests de publicación observados en logs**:

| Paquete | Tag SHA (prefijo) | Digest comunicado en docker push; pendiente de contraste actual |
|---|---|---|
| medinet-pab-db | `c7a98b40…` | `sha256:880dbbf01bbc95333a63cda3806c21a66f00f685938df974b67561d4e4643dd0` |
| medinet-pab-api | `c7a98b40…` | `sha256:5d286f2e759a888a98fa98978522c745ea37b8a35d7397b4979de562be93db69` |
| medinet-pab-web | `c7a98b40…` | `sha256:66311a789125e112237b3f95e112f732c2912ecb96b59a617455eb514fd1736b` |
| medinet-pab-api | `5e45c59d…` | `sha256:f690e35cb999f0812ebaf1cb8850ec2d314eb40f37ffff3313a8445424789af7` |
| medinet-pab-web | `5e45c59d…` | `sha256:5107d394165c28ef1d9dcec2cc15dc2934de98bed954f53090d128d943245ce9` |
| medinet-pab-db | `5e45c59d…` | `sha256:22a4ac3569f968b60f13431a3491ecb264c00ebb446a76ace0ccd5db412ba20f` |
| medinet-pab-api | `add85a09…` | `sha256:a838de72c5a232a80f61b189597c8185ef50e7f3ca6f7a64ce2028e43eaf49e0` |
| medinet-pab-web | `add85a09…` | `sha256:2bfa1b91f38d0cd29be50fa6e889bfc86438f0dbfc062509918d72c581354c91` |
| medinet-pab-db | `add85a09…` | `sha256:70c268f57700573d002e280729fefcb425c6c0471d364f8df759cb7778958ae4` |

Los prefijos corresponden, sin ambigüedad, a estas etiquetas completas:

- sha-c7a98b40ecbba2f23aaf5c1ef8c37ef039a4b1be
- sha-5e45c59da77e38a7c551cbe24a90072293b2475b
- sha-add85a09a03fd0fa9f5410ea4e252e09540b3f67

### Contenido, Gitleaks y clasificación

Se reabrieron los tres bundles, extrayendo todos los archivos regulares de cada
capa sin el límite anterior de 5 MB; se examinaron también config/ENV e historial.
Se conservaron capas individuales, incluidas las ocultadas o borradas por capas
posteriores, sin levantar contenedores de la aplicación, modificar datos ni cargar
las imágenes sobre las locales. Los enlaces no se siguieron. No es un análisis
forense de binarios u ofuscación deliberada.

Gitleaks 8.30.1, digest ya documentado, escaneó el conjunto con red deshabilitada,
redacción total y sin agregar supresiones. Resultado: **6 alertas**, código de
salida **1**. Se mantienen como alertas, no se describe falsamente un exit 0:

| Imagen | Regla / ubicación | Clasificación |
|---|---|---|
| API c7a98b40… | generic-api-key; config, ENV e historial de build | 2 huellas públicas GPG de verificación Python; falso positivo |
| API 5e45c59… | misma regla y campos | 2 huellas públicas GPG; falso positivo |
| API add85a09… | misma regla y campos | 2 huellas públicas GPG; falso positivo |
| Web y DB, las tres versiones | Ninguna alerta Gitleaks | Sin secreto auténtico detectado |

El archivo cacert.pem es un conjunto de certificados públicos de certifi en una
capa base. Los SQL de extensiones y sistema de PostgreSQL son scripts del motor,
no respaldos ni filas de pacientes. No se encontraron .env operativos, claves
privadas, tokens GitHub/AWS, contraseñas o JWT reales en el material examinado.
La comparación de los secretos locales conocidos de 16 o más caracteres contra
config y bytes íntegros de todas las capas no encontró coincidencias. Los valores
cortos no permiten esa atribución automática; su limitación contextual fue
explicada en la auditoría inicial. El seed y recursos web recuperados corresponden
a demostración ficticia; no se identificaron bases precargadas con datos clínicos.

### Limitaciones concretas y cierre necesario

La lectura HTTPS directa con el namespace real en minúsculas
`ghcr.io/claudiopioenfasis/medinet-pab-{api,web,db}` devolvió **403 en las nueve
combinaciones**. Se utilizó únicamente autenticación existente y no se modificó.
Falta una autorización utilizable de **read:packages y lectura del paquete** para
consultar manifests privados. El intento adicional de acceso con Docker tampoco
permitió recuperar un manifest. No se solicitaron ni imprimieron tokens.

Ninguna de las nueve versiones carece ya de inspección de contenido de su
artefacto; las nueve carecen de comprobación independiente de **su resolución
actual tag→digest en GHCR**. Se conserva esta diferencia material para no aprobar
un tag que pudiera haber sido reasignado después del run inspeccionado.

Para cerrar sin compartir credenciales, el propietario puede comparar en GitHub
los nueve digests actuales de versión con la tabla anterior y registrar el
resultado por paquete/tag. Si todos coinciden, se vincula el inventario visual al
contenido auditado y se puede reevaluar A-01; si alguno difiere, hay que inspeccionar
esa versión exacta. Alternativamente, permitir lectura autorizada de manifests y
blobs por digest, sin ampliar a permisos de escritura o borrado. No bastan los
nombres de tags ni la cantidad de versiones. No cambiar visibilidad para sortear
la falta de acceso durante esta comprobación.

A-01 queda **parcialmente cerrado**: inventario confirmado por el propietario y
9/9 artefactos inspeccionados; falta el contraste de digests actuales. No se
confirmaron secretos que requieran revocación ni limpieza de historial. Permanecen
las medidas previas de no habilitar CD sin autorización, proteger main/production
cuando corresponda y no reutilizar la credencial DB local débil en EC2.

Solo se actualizaron este informe y su JSON publicable. Los scripts/reportes
auxiliares están bajo backups/publication-audit/final-ghcr, privado e ignorado.
No se cambiaron visibilidad, credenciales, archivos .env, código funcional,
versiones de GHCR, contenedores existentes, bases, volúmenes ni recursos AWS;
no se ejecutó push, force push o reescritura de historial.

### Recomendación final

La inspección de contenido se completó para las nueve imágenes conservadas en
Actions y no identificó secretos auténticos. Se mantiene la decisión conservadora
hasta contrastar los nueve digests actuales del registro; no se atribuye el
bloqueo a una filtración demostrada ni a que falten tres imágenes por inspeccionar.

**NO APTO PARA HACER PÚBLICO**
