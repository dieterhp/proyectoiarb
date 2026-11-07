# Río Claro IA: de datos dispersos a IA útil

**Proyecto integrador AI-901 · Microsoft Azure AI Fundamentals · Microsoft Foundry**
**caso de la Distribuidora Río Claro**

**Prototipo en línea:** https://rioclaro-dts.azurewebsites.net

| Integrantes
| Dieter Isaac Haefner Pérez |
| Mario Jose Santiago Sanchez |
| Juan Contreras Alvarado |
| Evelyn Daniela Sanchez Santos |

> Todos los datos (clientes, facturas, quejas, precios) son **ficticios** y se generaron para este proyecto.

---

## 1. El problema

Distribuidora Río Claro es una distribuidora de productos de limpieza e higiene con 140 empleados y 5 sucursales (Guadalajara, Zapopan, León, Querétaro y Aguascalientes). Quiere usar IA, pero su información está dispersa:

| Fuente | Cómo está hoy | Por qué frena a la IA |
|---|---|---|
| Facturas de proveedores | PDF y fotos en correos personales | El total vive dentro de una imagen; una factura se pagó dos veces |
| Catálogo | Un Excel por sucursal, con nombres distintos ("Cloro 1L", "CLORO LITRO", "Blanqueador 1000ml") | Sin fuente única, la IA daría datos contradictorios |
| Quejas | WhatsApp, llamadas y correos sin registro central | Sin historial no hay seguimiento ni análisis |
| Políticas | Tres versiones contradictorias de la política de devoluciones | La IA respondería con seguridad algo incorrecto |
| Permisos | Una contraseña compartida para todo | Riesgo de exponer nóminas y datos de clientes |

La dirección pide: (1) dejar de capturar facturas a mano y (2) un asistente que responda en minutos, no en días.

## 2. La solución

Un prototipo web, al que se entra con una liga, con tres pestañas:

1. **Asistente** (texto y voz): responde sobre inventario, precios, quejas y política de devoluciones, indica de qué documento salió la respuesta y avisa que es una IA.
2. **Facturas**: se sube un PDF o foto, se extraen proveedor, folio, fecha y total, se detectan duplicadas y las dudosas se mandan a **revisión humana**. Una persona aprueba.
3. **Quejas**: registro central con análisis de sentimiento y resumen por tipo.

_[Captura: pantalla general de la aplicación]_

![Pantalla general](img/01-general.png)

## 3. Arquitectura y servicios de Azure

| Componente | Servicio de Azure | Para qué se usa |
|---|---|---|
| Aplicación web | Azure App Service (Linux, Python 3.12, Flask) | Hospeda el prototipo |
| IA generativa | Microsoft Foundry con el modelo `gpt-4.1-mini` | Asistente conversacional |
| Extracción de facturas | Azure AI Document Intelligence (modelo `prebuilt-invoice`) | Lee proveedor, folio, fecha y total con nivel de confianza |
| Análisis de texto | Azure AI Language (análisis de sentimiento) | Clasifica las quejas |
| Voz | Azure AI Speech | Reconocimiento de voz y respuesta hablada |

```
Usuario (web / celular)
        │
        ▼
 Azure App Service (Flask)
   ├── /api/chat ───────► Microsoft Foundry (gpt-4.1-mini) + datos de Río Claro
   ├── /api/factura ────► Document Intelligence (prebuilt-invoice)
   ├── /api/quejas ─────► Azure AI Language (sentimiento)
   └── /api/speech-token ► Azure AI Speech (voz en el navegador)
```

**Por qué esta arquitectura:** el presupuesto del piloto es limitado y no hay personal técnico, así que se usó un solo recurso de IA (`AIServices`) con pago por uso, un modelo pequeño y una sola aplicación. No hay servidores que administrar.

_[Captura: grupo de recursos en el portal de Azure con los servicios creados]_

![Recursos en Azure](img/02-recursos-azure.png)

## 4. Cómo se ordenaron los datos

Antes de construir se ordenó lo indispensable:

- **Catálogo único:** los 5 catálogos de sucursal (con columnas y nombres distintos) se unificaron en `catalogo_unificado.csv`, con un SKU por producto (RC-001 a RC-015).
- **Inventario y ventas unificados** por SKU y sucursal.
- **Política vigente única:** de tres versiones contradictorias (8, 15 y 30 días) se definió una sola, de 15 días naturales, que es la que consulta el asistente.
- **Quejas centralizadas** en un solo registro, con cliente, sucursal y canal.

_[Captura: ejemplo de los catálogos originales frente al catálogo unificado]_

![Catálogos](img/03-catalogos.png)

## 5. Demostración

### 5.1 Asistente (texto)

El asistente responde solo con la información cargada y cita su fuente. Si no la tiene, lo dice y sugiere hablar con una persona.

![Inventario](img/04-chat-inventario.png)
![Política](img/05-chat-politica.png)
![Pregunta sin información](img/06-chat-sin-informacion.png)

### 5.2 Asistente (voz, desde el celular)

![Voz en celular](img/07-voz-celular.png)

### 5.3 Facturas

El flujo es: subir archivo → extracción → verificación de duplicados y confianza → aprobación humana.

![Factura extraída](img/08-factura-extraida.png)
![Factura duplicada](img/09-factura-duplicada.png)
![Factura borrosa en revisión humana](img/10-factura-borrosa.png)
![Factura aprobada por una persona](img/11-factura-aprobada.png)

**Resultados de las pruebas con las facturas de ejemplo:**

| Archivo | Extracción | Confianza | Resultado |
|---|---|---|---|
| `factura_001` (PDF) | Correcta (total $14,645) | 0.61 | Pendiente de aprobación |
| `factura_final2` (misma factura, otro nombre de archivo) | Correcta | 0.61 | **DUPLICADA** |
| `factura_003` (PDF) | Correcta (total $4,732.80) | 0.59 | Pendiente de aprobación |
| `foto_whatsapp_factura` (foto inclinada) | Correcta (total $3,445.20) | 0.80 | Pendiente de aprobación |
| `factura_borrosa` (imagen borrosa) | Sin datos | 0.00 | **REVISIÓN HUMANA** |

**Cómo se fijó el umbral de revisión.** La revisión humana se decide con la confianza mínima de los campos críticos para un pago (proveedor, folio y total). El umbral se fijó en **0.5**, por debajo de las facturas legibles (0.59 a 0.80) y por encima de la ilegible (0.00). Las facturas de ejemplo se generaron de forma sintética, por lo que Azure les asigna confianzas menores que a un CFDI real; con facturas reales convendría un umbral más alto.

> Una factura sin datos legibles **no se completa con valores inventados**: se marca para revisión.

### 5.4 Quejas

![Quejas con sentimiento](img/12-quejas.png)

Los reclamos repetidos del Hotel Real del Valle (cuatro por el mismo retraso en septiembre y uno más en octubre) quedan en un solo registro, con su sentimiento, que antes se perdían entre WhatsApp, llamadas y correos.

## 6. IA responsable

| Principio | Pregunta del caso | Evidencia en el prototipo |
|---|---|---|
| **Equidad** | ¿Trata igual a clientes de todas las sucursales? | El asistente usa un solo catálogo, un solo inventario y una sola política para las 5 sucursales. Prueba: la misma pregunta simulando clientes de cada sucursal. _(completar la tabla con los resultados reales)_ |
| **Confiabilidad y seguridad** | ¿Qué pasa si una factura está borrosa? | Se marca **REVISIÓN HUMANA** y no se inventa un total (captura 10). El asistente responde "no tengo esa información" cuando el dato no existe. |
| **Privacidad y seguridad** | ¿Se protegen nóminas, precios internos y datos sensibles? | Las nóminas y los costos no se cargan al modelo. Ante "¿cuánto gana el gerente de León?" responde que no tiene esa información y sugiere hablar con una persona (captura 6). La clave del servicio de IA se guarda como variable de entorno de App Service, no en el código ni en el repositorio. |
| **Inclusión** | ¿Funciona por voz y desde el celular? | Entrada y respuesta por voz con Azure AI Speech, y diseño adaptable a celular (capturas 7 y 12). |
| **Transparencia** | ¿El usuario sabe que habla con una IA y de dónde sale cada respuesta? | Aviso fijo "Estás hablando con una IA" y línea **Fuente:** con el documento usado en cada respuesta. |
| **Rendición de cuentas** | ¿Quién aprueba lo que sugiere la IA? | Ninguna factura queda aprobada sin que una persona pulse **Aprobar**, y el sistema registra quién aprobó (captura 11). |

## 7. Cómo atiende a cada personaje

| Personaje | Qué necesita | Qué ofrece el prototipo |
|---|---|---|
| **Don Ernesto**, director general | Cifras que coincidan entre sucursales | Catálogo, inventario y ventas unificados por SKU y sucursal |
| **Laura**, cuentas por pagar | Dejar de capturar a mano y evitar pagos duplicados | Extracción automática, detección de duplicadas y revisión solo de los casos dudosos, con aprobación humana |
| **Mariana**, gerente de León | Dar seguimiento a clientes molestos | Registro central de quejas con sentimiento; el asistente consulta el historial de cualquier cliente sin importar la sucursal |
| **Toño**, jefe de bodega | Consultar por voz desde el celular | Pregunta hablada ("¿cuánto cloro de litro nos queda?") con respuesta correcta |
| **Carlos**, soporte | Sistema que pueda controlar y apagar | Una sola aplicación administrada en App Service, que se detiene con un comando; el acceso por persona queda como mejora (ver sección 8) |

## 8. Limitaciones y siguientes pasos

Se documentan con honestidad, porque el prototipo es una demostración y no un sistema de producción:

- **Acceso:** el prototipo no tiene inicio de sesión. Para producción se propone Microsoft Entra ID con un rol por persona (Laura, gerentes, bodega) y permisos mínimos.
- **Secretos:** la clave está en variables de entorno de App Service. Lo recomendable es moverla a **Azure Key Vault** con identidad administrada.
- **Almacenamiento:** las facturas procesadas se guardan en un archivo temporal que se borra si la aplicación se reinicia. Para producción se usaría una base de datos (por ejemplo, Azure Cosmos DB o Azure SQL).
- **Datos:** el asistente recibe el catálogo, el inventario y las políticas dentro de su contexto, lo cual es viable con pocos datos. Con volúmenes reales conviene indexarlos con Azure AI Search.
- **Umbral de facturas:** calibrado con facturas sintéticas; debe recalibrarse con facturas reales.
- **Ventas:** no se implementó un panel de ventas por sucursal; los datos de ventas unificados quedaron preparados para ello.
- **Pagos:** el sistema nunca paga por sí solo; solo propone y una persona aprueba.

## 9. Cómo probarlo

1. Abrir https://rioclaro-dts.azurewebsites.net (la primera carga puede tardar unos segundos).
2. **Asistente:** probar las preguntas de ejemplo o hablarle con el botón del micrófono.
3. **Facturas:** subir una factura de ejemplo, luego la misma otra vez para ver la detección de duplicadas, y una imagen borrosa para ver la revisión humana.
4. **Quejas:** pulsar *Analizar sentimiento*.

## 10. Repositorio

Código fuente: https://github.com/dieterhp/proyectoiarb
