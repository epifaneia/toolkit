# toolkit

*Read this in [Español](README.es.md).*

The part of an AI pipeline that repeats in every project, already built. Each tool is anchored to one of the five design steps and comes out of a pipeline that has run on real data. A new pipeline is assembled by placing parts in steps 1 to 4 and spending the time on the one step that is always new: the output guardrail, the one that takes the shape of your destination.

> AI carries risk. Code bounds it. The standard answers for what remains.

[Design philosophy](#design-philosophy) · [Why this repository](#why-this-repository) · [Modules](#modules) · [Usage](#usage) · [Integration contract](#integration-contract) · [Limitations](#limitations) · [Security & regulation](#security--regulation)

---

## Design philosophy

Every AI application has five steps. Only step 4 invokes a model; the other four are code: reproducible, testable, offline. Step 5 never patches: it flags and degrades. Full text at [epifaneia.dev](https://epifaneia.dev).

```
 1 CLEANING      2 CONTEXT       3 INPUT GUARDRAIL   4 PROCESS        5 OUTPUT GUARDRAIL
 ■ code          ■ code          ■ code              ▲ model          ■ code
 kit.limpieza    kit.contexto    kit.guardarrail_in  kit.proceso      kit.guardarrail_out
                                                                      + kit.custodia (cross-cutting)
```

## Why this repository

Every project we take on leaves reusable material behind: reading documents whole, giving the model context it can cite, bounding what it may answer, verifying what it answered against the source, recording who ran it and who signed. Written once, tested on real data, ready for the next one.

That is what you get when a pipeline is built on this toolkit: it does not start from zero, it starts where the last one finished. The weeks that used to go into plumbing before touching the real problem go into the real problem, the output your destination demands. And the accumulation runs in your favour: every project adds tools, so each new one inherits everything learned on the previous ones. A second pipeline into Polarion, into an ERP or into a chat costs a fraction of the first.

Nothing here is a framework of our own invention. It is the current practice of the industry, assembled and tested: structured output, local models, deterministic verification, an integration contract with the company's own systems. There is nothing to learn on the side, and nothing to depend on that is not code you can read.

---

## Modules

One package per step. Every tool listed here is in the repository; the list grows as the tools do.

**1 · Cleaning** `kit.limpieza` · `text_norm` (Unicode and whitespace normalisation, stable for comparing and hashing).

**2 · Context** `kit.contexto` · `retrieve` (candidate chunks per item: the whole corpus when it fits the model's context, BM25 top-K when it does not; no embeddings, no network).

**3 · Input guardrail** `kit.guardarrail_in` · `citables` (splits a chunk into numbered units the model cites by index, so a quote is verbatim by construction).

**4 · Process** `kit.proceso` · `ollama` (local client, structured output, nothing leaves the machine), `gemini` (cloud client under the same contract, reports that data leaves), `json_helpers` (first valid JSON out of a model response).

**5 · Output guardrail** `kit.guardarrail_out` · `quote_verify` (the quote exists in the cited chunk, the page is derived from the offset, no evidence means degrade), `id_policy` (identifiers verbatim, derived, page-anchored or rejected, never invented), `roundtrip_diff` (the input file is sacred: three locks on the output XML).

**Cross-cutting** `kit.custodia` · `identity` (no run without a named actor, replaceable provider), `ledger` (one JSON line per model call, never the text), `signoff` and `cli` (an output is a proposal until a signed manifest verifies it).

## Usage

```bash
pip install -r requirements.txt
python tests/test_custodia.py          # local tests of the three wires, no network
```

```python
from kit.guardarrail_out.quote_verify import seal, citation
from kit.custodia.ledger import record_call

with record_call(step="s4", engine="ollama", endpoint="127.0.0.1:11434",
                 leaves_machine=False, payload=prompt):
    answer = client.generate(prompt)          # the model interprets

status, evidence, flags = seal(answer["status"], answer["evidence"],
                               chunk_by_id, open_value="Unconfirmed")   # the code guarantees
for ev in evidence:
    print(citation(ev))                       # [DOC p.81 §6.1] "quote..."
```

## Integration contract

The three `custodia` wires (identity, events, sign-off) ship with a local default and tests. The adapters to a company's identity provider, SIEM and signing mechanism are described in [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Limitations

- A kit of parts, not a framework: no orchestrator, no DSL, no UI. Each pipeline writes its own `run.py`.
- `roundtrip_diff` is written for ReqIF. The idea (locks on what may not change) applies to any XML; the code does not, yet.

---

## Security & regulation

Same four headings in every repository. Rows marked **today** are what the code does. Rows marked **wire** are the integration wires the company connects to its own systems: see [docs/INTEGRATION.md](docs/INTEGRATION.md).

| | | |
|---|---|---|
| **Confidentiality** | House rule: local by default. `proceso.ollama` is the default client; `proceso.gemini` exists for non-confidential data and comparison and reports that data leaves. | **today** |
| **Traceability** | **Wire 2 · events.** `custodia.ledger`: one JSON line per model call, never the text. `custodia.cli ledger` summarises it for the custody sheet. | **wire** |
| **Leak prevention** | **Wire 1 · identity.** `custodia.identity`: no run without a named actor; provider replaceable in one call. | **wire** |
| **Human in the loop** | `quote_verify.seal` degrades any status left without verified evidence and flags it. **Wire 3 · sign-off.** `custodia.signoff`: an output is a proposal until a manifest verifies. | **today / wire** |

Framework: EU AI Act (2024/1689) · GDPR · ISO/IEC 42001 · ISO/IEC 27001 · TISAX.

---

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
