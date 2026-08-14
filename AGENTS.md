# Instrucciones permanentes de SIGA

## Publicación obligatoria después de cada cambio

Todo cambio funcional aprobado debe entregarse en las dos aplicaciones y en todos los dispositivos:

1. Incrementar la versión de SIGA en todos los archivos correspondientes.
2. Sincronizar las fuentes y las copias empaquetadas de escritorio y móvil.
3. Compilar la aplicación de PC con PyInstaller para x86 y x64 desde la misma fuente.
4. Generar los ejecutables, ZIP e instaladores de x86 y x64, mantener los alias
   x64 heredados y actualizar `version.json` con todos sus hashes SHA-256.
5. Actualizar la instalación local de PC en `%LOCALAPPDATA%\SIGA` y verificarla.
6. Publicar el paquete y el manifiesto de PC en `dibenedettileonardo2014-dotcom/SIGA-actualizaciones`, rama `main`, para activar la actualización automática.
7. Publicar la aplicación móvil en Firebase Hosting, proyecto `siga-85bdd`.
8. Verificar el manifiesto remoto y el despliegue móvil antes de informar que el trabajo terminó.

El usuario autoriza este flujo habitual de compilación y publicación después de cada cambio y versión nueva. Si una herramienta solicita una confirmación de seguridad obligatoria, se debe pedir igualmente.

## Mantenimiento obligatorio de Windows x86 y x64

SIGA x86 y SIGA x64 forman un único producto. Toda función, corrección,
optimización, cambio visual, cambio de Firebase, seguridad, dependencia,
instalador o actualizador debe implementarse en la base de código común y
entregarse con el mismo número de versión y la misma funcionalidad en ambas
arquitecturas. No crear ramas funcionales independientes por arquitectura.

Ningún cambio puede considerarse terminado hasta:

1. Compilar con los intérpretes Python x86 y x64.
2. Ejecutar las pruebas comunes y las validaciones de cabecera PE.
3. Verificar que ambos ZIP contienen exactamente la fuente web vigente.
4. Comprobar que el manifiesto publica la misma versión para x86 y x64.
5. Confirmar que cada canal automático descarga exclusivamente su arquitectura.
6. Probar el inicio de ambas compilaciones y publicar ambos artefactos juntos.

La publicación debe abortarse ante versiones diferentes, fuente desactualizada,
arquitecturas cruzadas, hashes incorrectos o ausencia de cualquiera de los dos
paquetes.

## Conservación de versiones

Mantener siempre únicamente las dos versiones más recientes de SIGA y sus
instaladores en el estado vigente del proyecto. Al publicar una versión nueva,
eliminar los instaladores anteriores que excedan ese límite. Las versiones
retiradas permanecen recuperables desde el historial de Git.

## Costo operativo obligatorio

SIGA debe permanecer compatible con Firebase Spark y mantener costo operativo
$0. No incorporar Cloud Functions, servicios que requieran Blaze, facturación,
tarjeta, APIs pagas ni almacenamiento remoto de adjuntos. Antes de agregar una
dependencia o servicio, verificar que funcione íntegramente en Spark. Priorizar
Firestore, Authentication por correo, Hosting, reglas y transacciones cliente
dentro de sus cuotas gratuitas, minimizando lecturas, escrituras y transferencia.
