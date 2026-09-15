# La Democracia Optimista en breve

Cartera del autor: 0xcc7edd6b8bcb5febcc62cf47b4923a8267831e56
Publicado: 2026-09-14

Traduccion al espanol de la pagina de referencia de la campana "Optimistic
Democracy in brief". Todo el contenido procede de esa pagina.

GenLayer resuelve las transacciones que requieren juicio mediante un proceso
llamado Democracia Optimista.

Un validador lider propone un resultado para la transaccion. Otro grupo de
validadores repite el mismo trabajo de forma independiente y vota si el
resultado del lider es aceptable segun la regla de equivalencia del contrato.

Si la mayoria esta de acuerdo, el resultado se acepta de forma optimista. Se
vuelve definitivo cuando termina un periodo de apelacion sin una impugnacion
exitosa.

Cualquiera que no este de acuerdo con un resultado aceptado puede apelar
durante ese periodo. Una apelacion incorpora a un grupo mayor de validadores,
que evaluan la transaccion de nuevo.

El principio de equivalencia indica a los validadores cuando dos resultados
cuentan como iguales, de modo que los nodos honestos cuyas respuestas solo
difieren en la redaccion pueden coincidir.

Los validadores tienen participacion en riesgo, lo que da a cada uno una razon
para evaluar con honestidad en lugar de seguir al lider.
