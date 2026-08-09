# Instrucciones permanentes de SIGA

## Publicación obligatoria después de cada cambio

Todo cambio funcional aprobado debe entregarse en las dos aplicaciones y en todos los dispositivos:

1. Incrementar la versión de SIGA en todos los archivos correspondientes.
2. Sincronizar las fuentes y las copias empaquetadas de escritorio y móvil.
3. Compilar la aplicación de PC con PyInstaller.
4. Generar `SIGA.exe`, `SIGA-update.zip` y actualizar `version.json` con sus hashes SHA-256.
5. Actualizar la instalación local de PC en `%LOCALAPPDATA%\SIGA` y verificarla.
6. Publicar el paquete y el manifiesto de PC en `dibenedettileonardo2014-dotcom/SIGA-actualizaciones`, rama `main`, para activar la actualización automática.
7. Publicar la aplicación móvil en Firebase Hosting, proyecto `siga-85bdd`.
8. Verificar el manifiesto remoto y el despliegue móvil antes de informar que el trabajo terminó.

El usuario autoriza este flujo habitual de compilación y publicación después de cada cambio y versión nueva. Si una herramienta solicita una confirmación de seguridad obligatoria, se debe pedir igualmente.

## Conservación de versiones

Mantener siempre únicamente las dos versiones más recientes de SIGA y sus
instaladores en el estado vigente del proyecto. Al publicar una versión nueva,
eliminar los instaladores anteriores que excedan ese límite. Las versiones
retiradas permanecen recuperables desde el historial de Git.
