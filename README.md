# SIGA

Sistema Integral de Gestión de Afiliados y aplicación móvil **Mi SIGA**.

## Estructura

- `index.html`: panel administrativo de escritorio.
- `afiliado.html`: fuente de la PWA para afiliados.
- `assets/`: iconos, logotipo y Convenio Colectivo 77/89.
- `hosting/`: contenido publicado en Firebase Hosting.
- `installer/`: instaladores x86 y x64 de las dos versiones más recientes.
- `release/x86/SIGA/` y `release/x64/SIGA/`: compilaciones vigentes por arquitectura.
- `_internal/`, `SIGA.exe` y `SIGA-update.zip`: alias x64 para instalaciones
  anteriores; los artefactos con sufijo `-x86`/`-x64` son los canales nativos.
- `desktop_launcher.py`, `SIGA.spec` y `siga-installer.iss`: fuentes de
  compilación y empaquetado.
- `firebase.json` y `firestore.rules`: configuración de hosting y seguridad.

## Versión vigente

`1.4.44` — actualización con respaldo, confirmación de arranque y rollback.

Aplicación móvil: https://siga-85bdd.web.app/

El proyecto funciona exclusivamente con Firebase Spark: Hosting, Authentication
por correo y una única base Firestore dentro de sus cuotas gratuitas. No utiliza
Cloud Functions, Firebase Storage, APIs pagas ni servicios que requieran Blaze.

## Versiones conservadas

- 1.4.44 (x86 y x64)
- 1.4.43 (x86 y x64)

Los instaladores se encuentran en `installer/`.

## Publicación de una versión

1. Actualizar la versión en `desktop_launcher.py`, `index.html`,
   `afiliado.html`, `sw.js` y `siga-installer.iss`.
2. Sincronizar `afiliado.html` y `sw.js` con `hosting/`.
3. Compilar `SIGA.spec` con Python x86 y x64, generar ambos ZIP e instaladores,
   verificar sus arquitecturas PE y actualizar todos los hashes de `version.json`.
4. Publicar primero GitHub para habilitar la actualización de escritorio y
   después ejecutar `firebase deploy` para actualizar Mi SIGA.

La aplicación de escritorio consulta `version.json` al iniciar. La PWA fuerza
la comprobación de su service worker al abrir y recarga cuando hay una edición
nueva.

### Actualizaciones desde el programa

El escritorio consulta los manifiestos oficiales de GitHub y Firebase al abrir,
al recuperar conexión y periódicamente. Compara versión y revisión; descarga el
ZIP de su arquitectura y verifica SHA-256, tamaño, rutas y cabecera PE.
**Actualizar y reiniciar** aparece al estar listo; también se aplica al volver a
abrir SIGA. Una falta de conexión no impide usar la versión instalada.

Desde 1.4.44, el actualizador espera el cierre, respalda únicamente archivos del
programa, actualiza la carpeta del ejecutable en uso y elimina el pedido pendiente
antes del relanzamiento. La ventana nueva confirma versión y revisión. Si no
confirma dentro de 90 segundos, restaura y abre la versión anterior. El registro
`Updater/transaction.json` permite recuperar una transacción interrumpida al
arrancar; `Updater/backup` conserva el respaldo. Una revisión que hizo rollback
no se descarga repetidamente: se espera una revisión corregida.

No se reemplazan `WebViewProfile`, `Documentos`, configuración, bases locales ni
`oauth-password-reset.dat`. El origen local y el perfil siguen siendo los mismos.
No se modifican Firestore, Authentication, reglas ni el plan Spark.

Los equipos que tienen 1.4.43 reciben 1.4.44 por el canal ZIP existente. La primera
transición ejecuta el actualizador antiguo; las siguientes usan el mecanismo con
rollback de 1.4.44. No es posible modificar a distancia un equipo que nunca tuvo
un canal de actualización operativo o que no puede conectarse al repositorio.

Para futuras publicaciones, incrementar versión/revisión y sincronizar las
fuentes; compilar `SIGA.spec` con `.venv` (x64) y `.venv-x86`; compilar
`siga-installer.iss` con `/DMyAppArch=x64` y `/DMyAppArch=x86`; ejecutar
`python tools/package_release.py` para generar paquetes, alias y hashes.
Ejecutar las pruebas Python con ambos intérpretes y `tests/test_*.cjs` con Node.
Conservar las dos últimas versiones y publicar todos los artefactos junto con
`version.json` en la rama `main` del repositorio oficial; luego publicar Hosting
en `siga-85bdd`. No publicar solo el ejecutable ni cambiar el canal por un instalador.

Prueba real reproducible en una instalación aislada (requiere escritorio Windows):
`python tests/update_e2e.py x64 published` y lo mismo con `x86`.
La prueba abre 1.4.43, invoca su API nativa existente, descarga la versión publicada,
actualiza, reinicia WebView2 y verifica archivos y un valor persistido en el perfil.
Los modos `worker` y `rollback` prueban el reemplazo nuevo y una confirmación de
arranque fallida. No usan ni alteran los datos de la instalación real.
