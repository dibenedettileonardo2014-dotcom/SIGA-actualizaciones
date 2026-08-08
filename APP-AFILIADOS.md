# Mi SIGA — aplicación para afiliados

La aplicación se abre desde `afiliado.html` y se puede instalar en Android,
iPhone y computadoras como PWA. El afiliado ingresa con su DNI (sin puntos) y
la contraseña inicial entregada por el sindicato.

Después del primer ingreso, el afiliado puede activar el desbloqueo del
dispositivo mediante WebAuthn. En Android, Chrome solicita la huella, el rostro
o el PIN configurado en el teléfono. Mi SIGA conserva solamente el identificador
público de esa credencial y nunca almacena la contraseña ni los datos biométricos.

Aplicación publicada: https://siga-85bdd.web.app/

## Puesta en funcionamiento

La configuración de Authentication, las reglas de `firestore.rules` y Firebase
Hosting fueron publicadas el 7 de agosto de 2026. Para entregar un acceso:

1. En SIGA, autorizar el rol **Administrador** u **Operador** con su contraseña,
   abrir **Credencial
   Digital**, seleccionar al afiliado, escribir una contraseña inicial de ocho
   caracteres o más y pulsar **Crear acceso**.
2. Entregar al afiliado la URL pública, su DNI y la contraseña
   inicial. Desde **Mis datos** podrá cambiarla.

## Seguridad y funcionamiento

- El DNI se transforma internamente en un identificador de inicio de sesión;
  nunca se usa como contraseña.
- Cada credencial se guarda con el UID de Firebase Authentication. Las reglas
  permiten que un afiliado lea únicamente su propio documento.
- Las cuentas `administrador@siga.com` y `operador@siga.com` pueden crear,
  actualizar, bloquear o habilitar credenciales móviles después de validar su
  contraseña de rol.
- Los cambios realizados en el padrón se sincronizan con la credencial móvil
  de los afiliados que ya tengan acceso.
- La aplicación conserva localmente la última credencial para consulta sin
  conexión. Al cerrar sesión se elimina esa copia del dispositivo.
- El desbloqueo del dispositivo protege una sesión de Firebase ya iniciada. Si
  el afiliado cierra sesión, borra los datos de Chrome o cambia de teléfono,
  debe volver a ingresar una vez con DNI y contraseña y activar WebAuthn.
- Android verifica la huella, el rostro o el PIN dentro de su sistema seguro;
  Mi SIGA no puede leer ni conservar esos datos.

## Recuperación de acceso

La primera versión permite que el afiliado cambie su contraseña mientras tiene
la sesión abierta. Para una recuperación automática por olvido se debe cargar
y verificar un correo real por afiliado, o agregar una función de servidor que
permita al administrador emitir un restablecimiento temporal.
