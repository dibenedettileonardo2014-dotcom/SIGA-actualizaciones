# SIGA

Sistema Integral de Gestión de Afiliados y aplicación móvil **Mi SIGA**.

## Estructura

- `index.html`: panel administrativo de escritorio.
- `afiliado.html`: fuente de la PWA para afiliados.
- `assets/`: iconos, logotipo y Convenio Colectivo 77/89.
- `hosting/`: contenido publicado en Firebase Hosting.
- `installer/`: únicamente los dos instaladores más recientes.
- `release/SIGA/`: compilación vigente usada para generar el instalador.
- `_internal/`, `SIGA.exe` y `SIGA-update.zip`: paquete portable vigente y
  actualización automática.
- `desktop_launcher.py`, `SIGA.spec` y `siga-installer.iss`: fuentes de
  compilación y empaquetado.
- `firebase.json` y `firestore.rules`: configuración de hosting y seguridad.

## Versión vigente

`1.3.6` — auditoría integral, menor consumo de listeners móviles y retiro de Cambiar contraseña en la interfaz móvil.

Aplicación móvil: https://siga-85bdd.web.app/

El proyecto funciona exclusivamente con Firebase Spark: Hosting, Authentication
por correo y una única base Firestore dentro de sus cuotas gratuitas. No utiliza
Cloud Functions, Firebase Storage, APIs pagas ni servicios que requieran Blaze.

## Versiones conservadas

- 1.3.5
- 1.3.6

Los instaladores se encuentran en `installer/`.

## Publicación de una versión

1. Actualizar la versión en `desktop_launcher.py`, `index.html`,
   `afiliado.html`, `sw.js` y `siga-installer.iss`.
2. Sincronizar `afiliado.html` y `sw.js` con `hosting/`.
3. Compilar con `pyinstaller SIGA.spec`, generar `SIGA-update.zip` y el
   instalador, y actualizar los hashes de `version.json`.
4. Publicar primero GitHub para habilitar la actualización de escritorio y
   después ejecutar `firebase deploy` para actualizar Mi SIGA.

La aplicación de escritorio consulta `version.json` al iniciar. La PWA fuerza
la comprobación de su service worker al abrir y recarga cuando hay una edición
nueva.
