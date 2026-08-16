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

`1.4.15` — auditoría integral de rendimiento, funcionamiento offline, seguridad, sincronización y actualizaciones.

Aplicación móvil: https://siga-85bdd.web.app/

El proyecto funciona exclusivamente con Firebase Spark: Hosting, Authentication
por correo y una única base Firestore dentro de sus cuotas gratuitas. No utiliza
Cloud Functions, Firebase Storage, APIs pagas ni servicios que requieran Blaze.

## Versiones conservadas

- 1.4.15 (x86 y x64)
- 1.4.14 (x86 y x64)

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

### Actualización fluida desde 1.4.12

SIGA consulta el manifiesto sin caché, descarga en segundo plano el instalador
de su arquitectura y muestra **Reiniciar y actualizar** solamente después de
validar tamaño y SHA-256. Si la preparación falla, la versión instalada sigue
operativa. El relanzamiento usa siempre `%LOCALAPPDATA%\SIGA\SIGA.exe`.
