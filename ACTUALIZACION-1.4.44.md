# Verificación de SIGA 1.4.44

Fecha: 9 de septiembre de 2026. Revisión: `20260909-01`.
Publicación de aplicación: commit `b89e890`, rama `main`.

Se conservó la base común x86/x64 y no se modificaron las funciones de afiliados,
pagos, roles, autenticación, diagnósticos, PDF, datos ni reglas de Firebase.
Las modificaciones web son exclusivamente de versión y revisión.

## Por qué fallaba el mecanismo anterior

- Extraía el ZIP directamente sobre la instalación, sin respaldo ni confirmación
  de arranque ni rollback.
- Abría SIGA antes de retirar `prepared-update.json`: existía una carrera que
  podía volver a aplicar la misma actualización.
- Siempre escribía en `%LOCALAPPDATA%\SIGA`, aunque la instancia usada estuviera
  en otra carpeta; eso podía dejar accesos apuntando a una copia vieja.
- No utilizaba el mutex existente al descargar. En la prueba publicada se
  observaron descargas simultáneas y errores de acceso al archivo temporal.
- Hacía depender el reinicio del refresco de iconos. Se reprodujo que la copia
  x86 antigua, ejecutada en Windows x64, reemplaza los archivos pero aborta el
  reinicio porque `ie4uinit.exe` no existe en SysWOW64.
- La validación aceptaba cualquier repositorio alojado en GitHub.

## Archivos y necesidad de cada cambio

| Archivos | Motivo |
|---|---|
| `desktop_launcher.py` | Corregir el actualizador existente: exclusión de descargas simultáneas, repositorio oficial, reemplazo en la carpeta en uso, entrega al ayudante, confirmación de arranque y recuperación. |
| `update_worker.ps1` y `_internal/update_worker.ps1` | Ayudante externo del mismo actualizador: espera de cierre, respaldo, registro de reemplazo, reinicio, confirmación y restauración. No requiere refrescar iconos. |
| `SIGA.spec` | Empaquetar el ayudante en x86 y x64. |
| `index.html`, `_internal/index.html`, `afiliado.html`, `hosting/afiliado.html`, `sw.js`, `hosting/sw.js`, `siga-installer.iss` | Sincronizar exclusivamente versión/revisión y caché de la nueva publicación. |
| `version.json`, `hosting/version.json`, `release/version.json` | Publicar 1.4.44 con tamaños y SHA-256 de todos los artefactos. |
| `SIGA.exe`, `SIGA-x64.exe`, `SIGA-x86.exe`, ZIP e instaladores 1.4.44 y sus alias/copias de Hosting; `_internal/base_library.zip` | Artefactos generados a partir de la misma fuente. Se retiraron los instaladores y ZIP 1.4.42; se conservan 1.4.43 y 1.4.44. |
| `tools/package_release.py` | Hacer reutilizable el empaquetado, comprobando fuente web, ayudante y cabeceras PE y generando hashes para futuras versiones. |
| `tests/test_audit.py`, `tests/test_update_safety.py` | Actualizar expectativas del mecanismo anterior y comprobar seguridad, integridad, versión, datos protegidos y ausencia de ciclos. |
| `tests/update_e2e.py`, `tests/native_webview.cjs` | Prueba con ejecutables y WebView2 reales: versión previa, actualización, reinicio y persistencia. |
| `README.md`, este informe | Documentar publicación futura, evidencia y límites de la primera transición. |

## Funcionamiento resultante

1. El programa conserva la consulta nativa de los manifiestos de GitHub y
   Firebase, al iniciar y en los reintentos existentes.
2. Compara versión/revisión y selecciona exclusivamente x86 o x64 según su
   ejecutable. Descarga por HTTPS desde el repositorio oficial o su Hosting.
3. Verifica SHA-256, tamaño, rutas del ZIP y arquitectura PE. Un archivo alterado
   no habilita la instalación.
4. Muestra el aviso existente cuando está listo. Se aplica al pulsar actualizar
   y reiniciar o al siguiente inicio.
5. Espera el cierre y respalda solo los archivos del programa que va a reemplazar.
   Conserva perfil WebView, Documentos, archivos de usuario, configuración y
   credenciales; mantiene el mismo origen local y almacenamiento.
6. Retira la solicitud pendiente antes de relanzar. La nueva ventana debe
   confirmar versión y revisión dentro de 90 segundos. Si no lo hace, restaura
   y abre la versión anterior. Una revisión que hizo rollback no se ofrece
   indefinidamente; se espera una revisión corregida.

Publicación PC: `dibenedettileonardo2014-dotcom/SIGA-actualizaciones`, rama `main`.
Publicación móvil/espejo: Firebase Hosting, proyecto `siga-85bdd`.
No se incorporaron servicios, dependencias pagas ni cambios al plan Spark.

## Pruebas realizadas

- Compilación PyInstaller x86 y x64 e instaladores de ambas arquitecturas.
- 76 pruebas Python aprobadas con cada intérprete; las 7 pruebas JavaScript
  aprobaron autenticación y recuperación de red, diagnósticos, filtros,
  orden de PDF, navegación y permisos, aviso de actualización y versión.
- Validación PE, fuente web exacta dentro de ambos ZIP, ayudante empaquetado,
  misma versión y hashes del manifiesto.
- Sustitución 1.4.43 → 1.4.44 con el nuevo ayudante en x86 y x64: arranque real
  de WebView2, versión y arquitectura correctas; conservación de un valor en
  localStorage y de archivos de documento, base, configuración y credenciales
  sintéticos, comparados byte a byte.
- Fallo provocado de confirmación de arranque x64: después del plazo real de
  90 segundos, restauración del ejecutable original 1.4.43, relanzamiento real,
  mismo perfil y archivos intactos.
- Publicación real → detección por el ejecutable original 1.4.43 → descarga
  oficial → aplicación → reinicio y validación de datos: aprobada x64 y x86.
  En x86 sobre este Windows x64 fue necesario que el ayudante **antiguo** usara
  PowerShell nativo. Sin esa adaptación de prueba se reprodujo el fallo del
  refresco de iconos. No se alteró el ejecutable 1.4.43 para la prueba.
- API nativa del nuevo 1.4.44: aplicación del paquete verificado, entrega al
  ayudante empaquetado, reinicio y confirmación de salud comprobados en x86
  sin la adaptación anterior, y también en x64.
- Verificación remota: manifiestos de GitHub y Firebase idénticos al local,
  aplicación móvil 1.4.44 publicada y SHA-256 de ambos ZIP e instaladores correctos.

- Instalación local real `%LOCALAPPDATA%\SIGA`: actualización 1.4.43 → 1.4.44
  mediante su API existente, reinicio verificado, fuente web y ejecutable exactos,
  11 archivos existentes del usuario preservados. Accesos directos de Escritorio
  e Inicio verificados; SIGA quedó abierta normalmente, sin el puerto de depuración
  utilizado en las pruebas.

## Alcance de la primera transición

El código de 1.4.44 no puede ejecutarse antes de que lo entregue el actualizador
que ya está instalado. En copias antiguas x86 sobre Windows x64, el defecto del
refresco de iconos puede requerir **volver a abrir SIGA una vez** tras el reemplazo;
no requiere reinstalarlo ni visitar el equipo. Las siguientes actualizaciones
usan el mecanismo corregido y no tienen esa dependencia.

Las pruebas se ejecutaron en este Windows x64 con binarios reales de ambas
arquitecturas y datos aislados. No se inspeccionaron todos los equipos remotos ni
se ejecutó una máquina Windows de 32 bits. La prueba de rollback fue un arranque
sin confirmación, no un corte físico de energía.
