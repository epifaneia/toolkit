# toolkit

*Read this in [English](README.md).*

La parte de un pipeline de IA que se repite en cada proyecto, ya hecha. Cada herramienta va anclada a uno de los cinco pasos de diseño y sale de un pipeline que ha corrido sobre datos reales. Un pipeline nuevo se monta poniendo piezas en los pasos 1 a 4 y dedicando el tiempo al único paso que siempre es nuevo: el guardarraíl de salida, el que toma la forma de tu destino.

> La IA tiene riesgos. El código los acota. La norma responde de lo que queda.

[Filosofía de diseño](#filosofía-de-diseño) · [Por qué este repositorio](#por-qué-este-repositorio) · [Módulos](#módulos) · [Esqueleto](#esqueleto) · [Uso](#uso) · [Contrato de integración](#contrato-de-integración) · [Limitaciones](#limitaciones) · [Seguridad y regulación](#seguridad-y-regulación)

---

## Filosofía de diseño

Cualquier aplicación con IA tiene cinco pasos. Solo el paso 4 invoca un modelo; los otros cuatro son código: reproducibles, testeables, sin red. El paso 5 nunca corrige: marca y degrada. Texto completo en [epifaneia.dev](https://epifaneia.dev).

```
 1 LIMPIEZA      2 CONTEXTO      3 GUARDARRAÍL IN    4 PROCESO        5 GUARDARRAÍL OUT
 ■ código        ■ código        ■ código            ▲ modelo         ■ código
 kit.limpieza    kit.contexto    kit.guardarrail_in  kit.proceso      kit.guardarrail_out
                                                                      + kit.custodia (transversal)
                 kit.montaje los encadena: artefactos, checkpoints, actor
```

## Por qué este repositorio

Cada proyecto en el que entro deja material reutilizable: leer documentos enteros, dar al modelo contexto que pueda citar, acotar lo que responde, verificar lo que respondió contra la fuente, registrar quién lo ejecutó y quién firmó. Escrito una vez, probado sobre datos reales, listo para el siguiente.

Eso es lo que se lleva quien encarga un pipeline sobre este toolkit: no empieza de cero, empieza donde terminó el anterior. Las semanas que antes se iban en fontanería antes de tocar el problema real se van al problema real, la salida que exige su destino. Y la acumulación juega a su favor: cada proyecto suma herramientas, así que cada uno nuevo hereda todo lo aprendido en los anteriores. Un segundo pipeline hacia Polarion, hacia un ERP o hacia un chat cuesta una fracción del primero.

Nada de esto es un framework inventado por mí. Es la práctica actual de la industria, montada y probada: salida estructurada, modelos en local, verificación determinista, contrato de integración con los sistemas de la propia empresa. No hay nada que aprender aparte, ni nada de lo que depender que no sea código que se puede leer.

---

## Módulos

Un paquete por paso. Toda herramienta listada aquí está en el repositorio; la lista crece con las herramientas.

**1 · Limpieza** `kit.limpieza` · `text_norm` (normalización Unicode y de espacios, estable para comparar y hashear).

**2 · Contexto** `kit.contexto` · `retrieve` (chunks candidatos por ítem: el corpus entero cuando cabe en el contexto del modelo, BM25 top-K cuando no; sin embeddings, sin red).

**3 · Guardarraíl de entrada** `kit.guardarrail_in` · `citables` (trocea un chunk en unidades numeradas que el modelo cita por índice, así la cita es literal por construcción).

**4 · Proceso** `kit.proceso` · el único paso que llama a un modelo. Un contrato para todos los motores, en `contrato`: entra una `Peticion` (entrada, instrucción de sistema, schema, opciones), sale una `Respuesta` (salida, motor, modelo, meta), y hay tres errores: `NoDisponible` (sin clave, sin paquete, servicio parado: no se envió nada), `Rechazada` (el adaptador se niega a enviar: no cabe, supera el tope) y `RespuestaInvalida` (se envió y lo que volvió no sirve). `llamar()` es la única puerta al modelo y deja cada llamada en el libro de custodia.

| Adaptador | Motor | Adónde va el dato | Qué vigila |
|---|---|---|---|
| `ollama` | cualquier modelo de Ollama | se queda en la máquina | salida forzada por JSON Schema; no envía un prompt que Ollama recortaría en silencio, y descarta la respuesta si aun así lo recortó |
| `gemini` | Gemini `generateContent` | nube | `responseSchema` impuesto por la API; la clave va en una cabecera, nunca en la URL |
| `deep_research` | Interactions API de Gemini | nube | una investigación en segundo plano que tarda minutos: se consulta hasta que acaba, se concatenan todos los bloques de salida, tope de tiempo con el ID en el error |
| `jev` | Jev vía OpenRouter | nube, de pago | decide entre opciones cerradas; tope de gasto sumado del coste real que hay en el ledger; límite de tamaño |
| `whisper` | faster-whisper | se queda en la máquina | voz a texto con marca de duda por segmento; nunca descarta ni corrige un segmento |
| `kokoro` | Kokoro-82M | se queda en la máquina | texto a voz con una voz fijada, para poder comparar ejecuciones |
| `stub` | ninguno | a ningún sitio | mismo contrato, sin red y sin inteligencia: el pipeline corre sin conexión |

`motores` crea uno de ellos a partir de la variable `MOTOR`: cambiar de motor es configuración, no código. `json_helpers` (primer JSON válido de una respuesta de modelo).

**5 · Guardarraíl de salida** `kit.guardarrail_out` · `quote_verify` (la quote existe en el chunk citado, literal, empezando y acabando en límite de palabra y sin dejar fuera un «no» justo delante, o como paráfrasis que conserva cada cifra en orden, con su signo y su unidad, cada negación y una lista corta de opuestos como máximo/mínimo; lo que se devuelve es siempre el texto del documento; la página se deriva del offset; sin evidencia se degrada), `id_policy` (identificadores verbatim, derivados, anclados a página o rechazados, nunca inventados), `roundtrip_diff` (el fichero de entrada es sagrado: tres candados sobre el XML de salida).

**Montaje** `kit.montaje` · `cadena`. Tres reglas: un paso es una función de artefacto a artefacto; un artefacto es JSON plano; cada paso deja un checkpoint (`NN_paso.json`) que solo se reutiliza mientras no cambien su entrada ni su `version` declarada. Depurar el paso 5 no vuelve a pagar el paso 4. La cadena no corre sin un actor con nombre y lo deja en cada checkpoint.

**Transversal** `kit.custodia` · `identity` (sin actor con nombre no hay ejecución, proveedor sustituible), `ledger` (una línea JSON por llamada al modelo, nunca el texto), `signoff` y `cli` (la salida es una propuesta hasta que un manifiesto firmado la verifica).

## Esqueleto

`esqueleto/` es un pipeline completo con solo los pilares: cinco módulos cortos, una función cada uno, encadenados en `run.py`. Responde a una pregunta sobre el manual sintético de un electrodoméstico (`esqueleto/muestra/manual.txt`) con citas copiadas del documento, nunca escritas por el modelo.

| Paso | Módulo | Qué hace |
|---|---|---|
| 1 | `s1_limpieza` | documento → párrafos con id |
| 2 | `s2_contexto` | los 3 párrafos más afines a la pregunta (BM25, sin red) |
| 3 | `s3_guardarrail_in` | frases numeradas y un schema cuyas citas solo pueden ser esos números |
| 4 | `s4_proceso` | una llamada a través de `llamar()`; no sabe con qué modelo habla |
| 5 | `s5_guardarrail_out` | cambia cada número por la frase del documento, marca y degrada, nunca reescribe |

```bash
export CUSTODIA_ACTOR=tu.nombre                     # PowerShell: $env:CUSTODIA_ACTOR="tu.nombre"
python -m esqueleto.run                             # MOTOR=stub: sin red, sin claves
MOTOR=ollama python -m esqueleto.run "¿Qué significa E3?"
MOTOR=gemini python -m esqueleto.run "¿Qué significa E3?"    # necesita GEMINI_API_KEY en .env
```

Los mismos cinco módulos en las tres ejecuciones; solo cambia el objeto que recibe el paso 4. Los checkpoints y la propuesta final van a `data/esqueleto/`, la llamada al modelo a `logs/custody.jsonl`.

El paso 5 se gana el sitio incluso aquí. En mis ejecuciones con `qwen2.5:7b` el modelo a veces cita la frase correcta y aun así responde `sin_evidencia`. El paso 5 no adivina qué mitad es la buena: deja las dos y marca `incoherente:sin_evidencia_con_citas`.

## Uso

```bash
pip install -r requirements.txt
cp .env.example .env
python tests/todas.py                  # todas las pruebas locales: custodia, adaptadores del paso 4, montaje, esqueleto, verificación de citas. Sin red, sin claves
```

Una llamada al modelo, con cualquier motor:

```python
from kit.proceso.contrato import Peticion, llamar
from kit.proceso.ollama import Ollama          # o Gemini(), o Stub(): mismo contrato

schema = {"type": "object",
          "properties": {"estado": {"type": "string", "enum": ["cumple", "no_cumple", "sin_evidencia"]}},
          "required": ["estado"]}

r = llamar(Ollama(), Peticion(entrada=prompt, schema=schema), paso="s4")   # el modelo interpreta, el ledger registra
print(r.salida["estado"], r.motor, r.modelo)
```

Un pipeline, encadenado:

```python
from functools import partial
from kit.montaje.cadena import Cadena, Paso

cadena = Cadena([
    Paso("s1_limpieza", limpiar),
    Paso("s4_proceso", partial(decidir, modelo=modelo), version=f"{modelo.motor}:{modelo.modelo}"),
    Paso("s5_guardarrail_out", verificar),
], carpeta="data/run")
salida = cadena.correr({"documento": "manual.txt"})          # después: python -m kit.custodia.cli sign <fichero>
```

`esqueleto/run.py` es la versión completa de los dos fragmentos.

## Contrato de integración

Los tres cables de `custodia` (identidad, eventos, firma) vienen con un valor local por defecto y pruebas. Los adaptadores al proveedor de identidad, al SIEM y al mecanismo de firma de cada empresa se describen en [docs/INTEGRATION.es.md](docs/INTEGRATION.es.md).

## Limitaciones

- Es un kit de piezas, no un framework: no hay DSL ni UI. `kit.montaje.cadena` encadena funciones y guarda checkpoints, nada más; cada pipeline sigue escribiendo su `run.py`.
- Solo el adaptador de Ollama se ha ejecutado contra su servicio desde este repositorio (el esqueleto con `qwen2.5:7b`). Los demás se prueban sin red contra imitaciones de su servicio, y sus llamadas siguen el código del que salen en mis otros proyectos.
- `deep_research` devuelve texto, sin schema: la estructura la saca una segunda llamada con salida forzada. `jev` usa un endpoint alfa de OpenRouter; el precio del código se comprobó el 2026-10-28 y puede cambiar.
- `whisper`, `kokoro` y `deep_research` necesitan paquetes que no están en `requirements.txt` (figuran ahí como opcionales); Whisper y Kokoro descargan sus pesos la primera vez.
- `quote_verify` no entiende el texto. Compara cifras, negaciones y una lista corta de opuestos, así que una paráfrasis que mueve una negación a otra cláusula, o cambia dos palabras fuera de esa lista, sigue pasando como aproximada; `seal` marca para revisar antes de firmar un veredicto que solo tiene citas aproximadas.
- `roundtrip_diff` está escrito para ReqIF. La idea (candados sobre lo que no puede cambiar) vale para cualquier XML; el código, todavía no.

---

## Seguridad y regulación

Los mismos cuatro epígrafes en todos los repositorios. Las filas **hoy** son lo que hace el código. Las filas **cable** son los cables de integración que la empresa conecta a sus sistemas: ver [docs/INTEGRATION.es.md](docs/INTEGRATION.es.md).

| | | |
|---|---|---|
| **Confidencialidad** | Regla de la casa: local por defecto. `ollama`, `whisper` y `kokoro` corren en la máquina; `gemini`, `deep_research` y `jev` declaran que el dato sale, y el ledger lo registra en cada llamada. El esqueleto usa el stub por defecto. Las claves solo vienen del entorno. | **hoy** |
| **Trazabilidad** | **Cable 2 · eventos.** `custodia.ledger`: una línea JSON por llamada al modelo, nunca el texto. Todos los adaptadores pasan por `proceso.contrato.llamar`. `custodia.cli ledger` lo resume para la ficha de custodia. | **cable** |
| **Prevención de fugas** | **Cable 1 · identidad.** `custodia.identity`: sin actor con nombre no hay ejecución; proveedor sustituible en una llamada. `montaje.cadena` lo comprueba antes del primer paso. | **cable** |
| **Humano en el bucle** | `quote_verify.seal` y el paso 5 del esqueleto degradan cualquier estado sin evidencia verificada y lo marcan. **Cable 3 · firma.** `custodia.signoff`: la salida es una propuesta hasta que un manifiesto verifica. | **hoy / cable** |

Marco: EU AI Act (2024/1689) · RGPD · ISO/IEC 42001 · ISO/IEC 27001 · TISAX.

---

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
