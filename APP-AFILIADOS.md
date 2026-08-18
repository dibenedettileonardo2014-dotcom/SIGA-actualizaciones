# Mi SIGA — aplicación para afiliados

La aplicación se abre desde `afiliado.html` y se puede instalar en Android,
iPhone y computadoras como PWA. El afiliado ingresa con su DNI (sin puntos) y
la contraseña inicial entregada por el sindicato.

Después del primer ingreso, el afiliado puede activar el desbloqueo del
dispositivo mediante WebAuthn. En Android, Chrome solicita la huella, el rostro
o el PIN configurado en el teléfono. Mi SIGA conserva solamente el identificador
público de esa credencial y nunca almacena la contraseña ni los datos biométricos.
La aplicación pregunta si desea activarlo después del primer ingreso y, una vez
configurado, intenta abrir automáticamente la verificación al iniciar. El botón
de desbloqueo queda disponible como alternativa si Android impide el inicio
automático.

Aplicación publicada: https://siga-85bdd.web.app/

La sección **Familia** muestra exclusivamente el grupo familiar cargado en la
ficha del afiliado: pareja e hijos, con nombre, DNI y edad. Los cambios se
sincronizan al guardar la ficha desde SIGA.

La aplicación de escritorio guarda cada cambio primero en la PC y mantiene una
cola local. Cuando recupera conexión, la cola se publica en Firebase y las demás
computadoras reciben el cambio mediante la sincronización en tiempo real.

## Puesta en funcionamiento

La configuración de Authentication, las reglas de `firestore.rules` y Firebase
Hosting fueron publicadas el 7 de agosto de 2026. Para entregar un acceso:

1. Al guardar un afiliado nuevo, SIGA crea automáticamente su acceso con la
   contraseña inicial `sindicatoquimico`. El rol **Administrador** puede
   administrar posteriormente ese acceso desde **Credencial Digital**.
2. Entregar al afiliado la URL pública, su DNI y la contraseña inicial.

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

Mi SIGA no permite cambiar ni recuperar la contraseña desde el teléfono. Si el
afiliado pierde el acceso, el administrador debe usar **Recuperar contraseña en
Firebase** desde la sección Credencial Digital. SIGA abre Firebase
Authentication y copia el identificador de la cuenta; Firebase es el único
componente que puede modificar esa contraseña sin exponer privilegios de
administración en la aplicación cliente. Este procedimiento sigue siendo
compatible con el plan Spark y no requiere servicios pagos.
