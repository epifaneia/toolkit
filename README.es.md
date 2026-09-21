# toolkit

*Read this in [English](README.md).*

La parte de un pipeline de IA que se repite en cada proyecto, ya hecha. Cada herramienta va anclada a uno de los cinco pasos de diseño y sale de un pipeline que ha corrido sobre datos reales. Un pipeline nuevo se monta poniendo piezas en los pasos 1 a 4 y dedicando el tiempo al único paso que siempre es nuevo: el guardarraíl de salida, el que toma la forma de tu destino.

> La IA tiene riesgos. El código los acota. La norma responde de lo que queda.

[Filosofía de diseño](#filosofía-de-diseño) · [Por qué este repositorio](#por-qué-este-repositorio) · [Módulos](#módulos) · [Uso](#uso) · [Contrato de integración](#contrato-de-integración) · [Limitaciones](#limitaciones) · [Seguridad y regulación](#seguridad-y-regulación)

---

## Filosofía de diseño

Cualquier aplicación con IA tiene cinco pasos. Solo el paso 4 invoca un modelo; los otros cuatro son código: reproducibles, testeables, sin red. El paso 5 nunca corrige: marca y degrada. Texto completo en [epifaneia.dev](https://epifaneia.dev).

```
 1 LIMPIEZA      2 CONTEXTO      3 GUARDARRAÍL IN    4 PROCESO        5 GUARDARRAÍL OUT
 ■ código        ■ código        ■ código            ▲ modelo         ■ código
 kit.limpieza    kit.contexto    kit.guardarrail_in  kit.proceso      kit.guardarrail_out
                                                                      + kit.custodia (transversal)
```

## Por qué este repositorio

Cada proyecto en el que entramos deja material reutilizable: leer documentos enteros, dar al modelo contexto que pueda citar, acotar lo que responde, verificar lo que respondió contra la fuente, registrar quién lo ejecutó y quién firmó. Escrito una vez, probado sobre datos reales, listo para el siguiente.

Eso es lo que se lleva quien encarga un pipeline sobre este toolkit: no empieza de cero, empieza donde terminó el anterior. Las semanas que antes se iban en fontanería antes de tocar el problema real se van al problema real, la salida que exige su destino. Y la acumulación juega a su favor: cada proyecto suma herramientas, así que cada uno nuevo hereda todo lo aprendido en los anteriores. Un segundo pipeline hacia Polarion, hacia un ERP o hacia un chat cuesta una fracción del primero.

Nada de esto es un framework inventado por nosotros. Es la práctica actual de la industria, montada y probada: salida estructurada, modelos en local, verificación determinista, contrato de integración con los sistemas de la propia empresa. No hay nada que aprender aparte, ni nada de lo que depender que no sea código que se puede leer.

---

## Módulos

Un paquete por paso. Toda herramienta listada aquí está en el repositorio; la lista crece con las herramientas.

**1 · Limpieza** `kit.limpieza` · `text_norm` (normalización Unicode y de espacios, estable para comparar y hashear).

**2 · Contexto** `kit.contexto` · `retrieve` (chunks candidatos por ítem: el corpus entero cuando cabe en el contexto del modelo, BM25 top-K cuando no; sin embeddings, sin red).

**3 · Guardarraíl de entrada** `kit.guardarrail_in` · `citables` (trocea un chunk en unidades numeradas que el modelo cita por índice, así la cita es literal por construcción).

**4 · Proceso** `kit.proceso` · `ollama` (cliente local, salida estructurada, nada sale de la máquina), `gemini` (cliente de nube con el mismo contrato, informa de que el dato sale), `json_helpers` (primer JSON válido de una respuesta de modelo).

**5 · Guardarraíl de salida** `kit.guardarrail_out` · `quote_verify` (la quote existe en el chunk citado, la página se deriva del offset, sin evidencia se degrada), `id_policy` (identificadores verbatim, derivados, anclados a página o rechazados, nunca inventados), `roundtrip_diff` (el fichero de entrada es sagrado: tres candados sobre el XML de salida).

**Transversal** `kit.custodia` · `identity` (sin actor con nombre no hay ejecución, proveedor sustituible), `ledger` (una línea JSON por llamada al modelo, nunca el texto), `signoff` y `cli` (la salida es una propuesta hasta que un manifiesto firmado la verifica).

## Uso

```bash
pip install -r requirements.txt
python tests/test_custodia.py          # pruebas locales de los tres cables, sin red
```

```python
from kit.guardarrail_out.quote_verify import seal, citation
from kit.custodia.ledger import record_call

with record_call(step="s4", engine="ollama", endpoint="127.0.0.1:11434",
                 leaves_machine=False, payload=prompt):
    answer = client.generate(prompt)          # el modelo interpreta

status, evidence, flags = seal(answer["status"], answer["evidence"],
                               chunk_by_id, open_value="Unconfirmed")   # el código garantiza
for ev in evidence:
    print(citation(ev))                       # [DOC p.81 §6.1] "quote..."
```

## Contrato de integración

Los tres cables de `custodia` (identidad, eventos, firma) vienen con un valor local por defecto y pruebas. Los adaptadores al proveedor de identidad, al SIEM y al mecanismo de firma de cada empresa se describen en [docs/INTEGRATION.es.md](docs/INTEGRATION.es.md).

## Limitaciones

- Es un kit de piezas, no un framework: no hay orquestador, no hay DSL, no hay UI. Cada pipeline escribe su `run.py`.
- `roundtrip_diff` está escrito para ReqIF. La idea (candados sobre lo que no puede cambiar) vale para cualquier XML; el código, todavía no.

---

## Seguridad y regulación

Los mismos cuatro epígrafes en todos los repositorios. Las filas **hoy** son lo que hace el código. Las filas **cable** son los cables de integración que la empresa conecta a sus sistemas: ver [docs/INTEGRATION.es.md](docs/INTEGRATION.es.md).

| | | |
|---|---|---|
| **Confidencialidad** | Regla de la casa: local por defecto. `proceso.ollama` es el cliente por defecto; `proceso.gemini` existe para dato no confidencial y comparación, e informa de que el dato sale. | **hoy** |
| **Trazabilidad** | **Cable 2 · eventos.** `custodia.ledger`: una línea JSON por llamada al modelo, nunca el texto. `custodia.cli ledger` lo resume para la ficha de custodia. | **cable** |
| **Prevención de fugas** | **Cable 1 · identidad.** `custodia.identity`: sin actor con nombre no hay ejecución; proveedor sustituible en una llamada. | **cable** |
| **Humano en el bucle** | `quote_verify.seal` degrada cualquier estado sin evidencia verificada y lo marca. **Cable 3 · firma.** `custodia.signoff`: la salida es una propuesta hasta que un manifiesto verifica. | **hoy / cable** |

Marco: EU AI Act (2024/1689) · RGPD · ISO/IEC 42001 · ISO/IEC 27001 · TISAX.

---

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
