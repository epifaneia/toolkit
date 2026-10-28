# toolkit

*Read this in [Español](README.es.md).*

The part of an AI pipeline that repeats in every project, already built. Each tool is anchored to one of the five design steps and comes out of a pipeline that has run on real data. A new pipeline is assembled by placing parts in steps 1 to 4 and spending the time on the one step that is always new: the output guardrail, the one that takes the shape of your destination.

> AI carries risk. Code bounds it. The standard answers for what remains.

[Design philosophy](#design-philosophy) · [Why this repository](#why-this-repository) · [Modules](#modules) · [Skeleton](#skeleton) · [Usage](#usage) · [Integration contract](#integration-contract) · [Limitations](#limitations) · [Security & regulation](#security--regulation)

---

## Design philosophy

Every AI application has five steps. Only step 4 invokes a model; the other four are code: reproducible, testable, offline. Step 5 never patches: it flags and degrades. Full text at [epifaneia.dev](https://epifaneia.dev).

```
 1 CLEANING      2 CONTEXT       3 INPUT GUARDRAIL   4 PROCESS        5 OUTPUT GUARDRAIL
 ■ code          ■ code          ■ code              ▲ model          ■ code
 kit.limpieza    kit.contexto    kit.guardarrail_in  kit.proceso      kit.guardarrail_out
                                                                      + kit.custodia (cross-cutting)
                 kit.montaje chains them: artefacts, checkpoints, actor
```

## Why this repository

Every project I take on leaves reusable material behind: reading documents whole, giving the model context it can cite, bounding what it may answer, verifying what it answered against the source, recording who ran it and who signed. Written once, tested on real data, ready for the next one.

That is what you get when a pipeline is built on this toolkit: it does not start from zero, it starts where the last one finished. The weeks that used to go into plumbing before touching the real problem go into the real problem, the output your destination demands. And the accumulation runs in your favour: every project adds tools, so each new one inherits everything learned on the previous ones. A second pipeline into Polarion, into an ERP or into a chat costs a fraction of the first.

Nothing here is a framework of my own invention. It is the current practice of the industry, assembled and tested: structured output, local models, deterministic verification, an integration contract with the company's own systems. There is nothing to learn on the side, and nothing to depend on that is not code you can read.

---

## Modules

One package per step. Every tool listed here is in the repository; the list grows as the tools do.

**1 · Cleaning** `kit.limpieza` · `text_norm` (Unicode and whitespace normalisation, stable for comparing and hashing).

**2 · Context** `kit.contexto` · `retrieve` (candidate chunks per item: the whole corpus when it fits the model's context, BM25 top-K when it does not; no embeddings, no network).

**3 · Input guardrail** `kit.guardarrail_in` · `citables` (splits a chunk into numbered units the model cites by index, so a quote is verbatim by construction).

**4 · Process** `kit.proceso` · the only step that calls a model. One contract for every engine, in `contrato`: a `Peticion` goes in (input, system instruction, schema, options), a `Respuesta` comes out (output, engine, model, meta), and there are three errors: `NoDisponible` (no key, no package, service down: nothing was sent), `Rechazada` (the adapter refuses to send: too large, over budget) and `RespuestaInvalida` (it was sent and what came back is unusable). `llamar()` is the single door to a model and writes every call to the custody ledger.

| Adapter | Engine | Where the data goes | What it guards |
|---|---|---|---|
| `ollama` | any Ollama model | stays on the machine | output forced by JSON Schema; refuses a prompt Ollama would silently truncate, and discards the answer if it was truncated anyway |
| `gemini` | Gemini `generateContent` | cloud | `responseSchema` imposed by the API; the key goes in a header, never in the URL |
| `deep_research` | Gemini Interactions API | cloud | background research that takes minutes: polled until done, every output block concatenated, time limit with the ID in the error |
| `jev` | Jev via OpenRouter | cloud, paid | decides between closed options; spending cap summed from the real cost in the ledger; size limit |
| `whisper` | faster-whisper | stays on the machine | speech to text with per-segment doubt flags; never drops or fixes a segment |
| `kokoro` | Kokoro-82M | stays on the machine | text to speech with a fixed voice, so runs can be compared |
| `stub` | none | nowhere | same contract, no network, no intelligence: the pipeline runs offline |

`motores` builds one of them from the `MOTOR` variable, so switching engine is configuration, not code. `json_helpers` (first valid JSON out of a model response).

**5 · Output guardrail** `kit.guardarrail_out` · `quote_verify` (the quote exists in the cited chunk, the page is derived from the offset, no evidence means degrade), `id_policy` (identifiers verbatim, derived, page-anchored or rejected, never invented), `roundtrip_diff` (the input file is sacred: three locks on the output XML).

**Assembly** `kit.montaje` · `cadena`. Three rules: a step is a function from artefact to artefact; an artefact is plain JSON; every step leaves a checkpoint (`NN_step.json`) that is reused only while its input and its declared `version` are unchanged. Debugging step 5 does not pay for step 4 again. The chain refuses to run without a named actor and stamps it on every checkpoint.

**Cross-cutting** `kit.custodia` · `identity` (no run without a named actor, replaceable provider), `ledger` (one JSON line per model call, never the text), `signoff` and `cli` (an output is a proposal until a signed manifest verifies it).

## Skeleton

`esqueleto/` is a complete pipeline with only the pillars: five short modules, one function each, chained in `run.py`. It answers a question about a synthetic appliance manual (`esqueleto/muestra/manual.txt`, in Spanish) with quotes copied from the document, never written by the model.

| Step | Module | What it does |
|---|---|---|
| 1 | `s1_limpieza` | document → paragraphs with an id |
| 2 | `s2_contexto` | the 3 paragraphs closest to the question (BM25, no network) |
| 3 | `s3_guardarrail_in` | numbered sentences, and a schema whose citations can only be those numbers |
| 4 | `s4_proceso` | one call through `llamar()`; it does not know which model it is talking to |
| 5 | `s5_guardarrail_out` | swaps each number for the document's sentence, flags and degrades, never rewrites |

```bash
export CUSTODIA_ACTOR=your.name                     # PowerShell: $env:CUSTODIA_ACTOR="your.name"
python -m esqueleto.run                             # MOTOR=stub: no network, no keys
MOTOR=ollama python -m esqueleto.run "¿Qué significa E3?"
MOTOR=gemini python -m esqueleto.run "¿Qué significa E3?"    # needs GEMINI_API_KEY in .env
```

Same five modules for the three runs; only the object step 4 receives changes. Checkpoints and the final proposal go to `data/esqueleto/`, the model call to `logs/custody.jsonl`.

Step 5 earns its place even here. In my runs with `qwen2.5:7b` the model sometimes cites the right sentence and still answers `sin_evidencia`. Step 5 does not guess which half is right: it keeps both and flags `incoherente:sin_evidencia_con_citas`.

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env
python tests/todas.py                  # every local test: custody, step 4 adapters, assembly, skeleton. No network, no keys
```

One model call, any engine:

```python
from kit.proceso.contrato import Peticion, llamar
from kit.proceso.ollama import Ollama          # or Gemini(), or Stub(): same contract

schema = {"type": "object",
          "properties": {"estado": {"type": "string", "enum": ["cumple", "no_cumple", "sin_evidencia"]}},
          "required": ["estado"]}

r = llamar(Ollama(), Peticion(entrada=prompt, schema=schema), paso="s4")   # the model interprets, the ledger records
print(r.salida["estado"], r.motor, r.modelo)
```

A pipeline, chained:

```python
from functools import partial
from kit.montaje.cadena import Cadena, Paso

cadena = Cadena([
    Paso("s1_limpieza", limpiar),
    Paso("s4_proceso", partial(decidir, modelo=modelo), version=f"{modelo.motor}:{modelo.modelo}"),
    Paso("s5_guardarrail_out", verificar),
], carpeta="data/run")
salida = cadena.correr({"documento": "manual.txt"})          # then: python -m kit.custodia.cli sign <file>
```

`esqueleto/run.py` is the full version of both snippets.

## Integration contract

The three `custodia` wires (identity, events, sign-off) ship with a local default and tests. The adapters to a company's identity provider, SIEM and signing mechanism are described in [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Limitations

- A kit of parts, not a framework: no DSL, no UI. `kit.montaje.cadena` chains functions and saves checkpoints, nothing more; each pipeline still writes its own `run.py`.
- Only the Ollama adapter has been run live from this repository (the skeleton with `qwen2.5:7b`). The others are tested offline against fakes of their services, and their calls follow the code they were extracted from in my other projects.
- `deep_research` returns text, no schema: structure comes from a second call with forced output. `jev` uses an alpha OpenRouter endpoint; its price in the code was checked on 2026-10-28 and may change.
- `whisper`, `kokoro` and `deep_research` need packages that are not in `requirements.txt` (listed there as optional); Whisper and Kokoro download their weights on first use.
- `roundtrip_diff` is written for ReqIF. The idea (locks on what may not change) applies to any XML; the code does not, yet.

---

## Security & regulation

Same four headings in every repository. Rows marked **today** are what the code does. Rows marked **wire** are the integration wires the company connects to its own systems: see [docs/INTEGRATION.md](docs/INTEGRATION.md).

| | | |
|---|---|---|
| **Confidentiality** | House rule: local by default. `ollama`, `whisper` and `kokoro` run on the machine; `gemini`, `deep_research` and `jev` declare that data leaves, and the ledger records it on every call. The skeleton defaults to the stub. Keys come from the environment only. | **today** |
| **Traceability** | **Wire 2 · events.** `custodia.ledger`: one JSON line per model call, never the text. Every adapter goes through `proceso.contrato.llamar`. `custodia.cli ledger` summarises it for the custody sheet. | **wire** |
| **Leak prevention** | **Wire 1 · identity.** `custodia.identity`: no run without a named actor; provider replaceable in one call. `montaje.cadena` checks it before the first step. | **wire** |
| **Human in the loop** | `quote_verify.seal` and the skeleton's step 5 degrade any status left without verified evidence and flag it. **Wire 3 · sign-off.** `custodia.signoff`: an output is a proposal until a manifest verifies. | **today / wire** |

Framework: EU AI Act (2024/1689) · GDPR · ISO/IEC 42001 · ISO/IEC 27001 · TISAX.

---

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
