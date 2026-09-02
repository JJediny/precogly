# 0005: Code execution over tools

Status: accepted as direction; revisited on a trigger, not a date
Date: 2026-07-31
Relates to: [0002](0002-tool-implementation-order.md),
[0003](0003-oauth-authorization-server.md), precogly/precogly #262, #259, #208, #261, #265

Precogly's API answers "tell me about this record". Agents ask "which records satisfy this
predicate". Every tool in [0002](0002-tool-implementation-order.md) has collided with that
gap, and each collision has been closed one at a time by adding a filter upstream or a
field to a projection. This records why that does not scale, and what does: giving the
model a sandboxed code API rather than a growing set of tools.

The tools in 0002 still get built. This is the ceiling they run into and the escape hatch,
measured.

## The collision

Four cases were recorded as the same shape. Checked one at a time, three of them were
something else, and the correction is more useful than the original claim.

| question | recorded as | what was true |
| --- | --- | --- |
| which models map to SOC 2? | no `framework` filter (#262) | the listing always returned `frameworks`; **0002's projection dropped it** |
| which threats map to CWE-20? | `search_fields` covers only name and description | true, and the entries are on every row — 33 rows / 38 KB filters client-side |
| which organization owns these rows? | filterable but not echoed (#259) | `/api/organizations/` is caller-scoped; one call settles it for a single-org caller |
| what is in the candidate pool? | the API offers only the ranked answer | stands |

The SOC 2 row is the one worth sitting with. It was recorded as an API limitation and it was
not one. [0002](0002-tool-implementation-order.md) dropped the field to save three queries
per row, which the server pays regardless because it is a `SerializerMethodField` in the list
serializer's `fields`. The saving was tokens, the price was a class of question, and the
trade was never stated because the measurement taken was of payload size. A local model
reading the raw response answered the question unaided while this was being written. The
field is now carried as bare names, at 18% of the row against 68% for the objects.

A projection is a capability decision wearing the costume of a size decision, and every tool
in [0002](0002-tool-implementation-order.md) makes one.

## What the arithmetic argument overstated

The first draft of this document said the fixes do not scale because one fix buys one
question. That is still the shape of the problem and it is not the reason it looked urgent.

An audit of `get_queryset` across `apps/` found nine query parameters on eight list routes
that are accepted and absent from the published schema, `threat_model` among them — it
narrows all three catalogs to the packs a model connects, on every one of them. It was never
missing. It was undiscoverable, because `filterset_fields` is empty on those viewsets so
drf-spectacular has nothing to introspect, and the parameters live in docstrings the
generator does not read.

So a share of "the API cannot do this" was "we could not find the parameter", and a share was
"we dropped the field ourselves". Both are cheaper to fix than an architecture, and neither
argues for one.

What survives is narrower. Filters answer predicates; they do not answer aggregates. No
`?framework=` produces the distribution of threats across taxonomies, or which
countermeasures recur across the most models, and no reasonable number of them ever will.
That class stays out of reach of the tool path however well documented it becomes.

The honest counter to this document's own recommendation is that a tool which fetches a
catalog and filters it in its body — which is what `search_threat_library` will do — is a
hardcoded instance of exactly what generated code would do. It works, it is cheap at this
catalog size, and it has the same ceiling: every question shape has to be chosen in advance,
written by us, and given a tool slot. That relocates the linear scaling from upstream PRs
into our own source. It does not remove it.

## Why tools do not scale

Tool-selection accuracy degrades with the number of tools in context. The measurement with
a stated method is [arXiv 2606.30317](https://arxiv.org/abs/2606.30317): Claude Haiku 4.5
holds 91% at 10 tools and 87% at 15; Sonnet 4 holds ≥90% to 20 and drops below by 30. The
recommendation is ≤10 tools per context.

Weigh it as observational rather than experimental. It is a retrospective analysis of one
organization's production telemetry — a latency-constrained voice deployment — with ground
truth taken from human post-call review, N=200 per bucket, and the session logs not
released, so the figures cannot be re-derived from the replication package. Two larger
studies it cites agree on direction: selection success above 90% only to ≈30 candidate
tools, degrading sharply past ≈100.

The planned surface is six tools, so nothing is on fire. The point is the gradient: the
per-question fix consumes the only budget that matters, and it is small.

## Why query generation is not ruled out

The obvious alternative is to let the model compose queries. The evidence usually cited
against it is Spider 2.0, where GPT-4o falls from 86.6% on Spider 1.0 to 10.1%, and
o1-preview reaches 17.1%.

That number is about a different population. Spider 2.0 selected for difficulty: every
database had to carry more than 200 columns or a nested schema, and the average is 812
columns. Its own error taxonomy attributes failure to exactly those properties — schema
linking 27.6% of errors, of which column linking is 16.6% and is attributed directly to
column count; JOIN errors 8.3%, because the BigQuery sources lack explicit foreign keys and
models must infer them; nested columns dropping accuracy from 68.04% to 18.51%.

Precogly has 560 columns across 57 models, 9.8 per model, and 107 declared foreign keys.
The entire application schema is smaller than one average Spider 2.0 database, the keys are
enforced by the ORM, and there are no nested columns. Every difficulty Spider 2.0 was built
to exhibit is absent.

This does not show query generation would work here. It removes the headline number from
the argument, which is different, and leaves the question open.

## What code execution changes

The pattern is Anthropic's: present the API to the model as functions it calls from code
rather than as tools it invokes, and run that code somewhere the intermediate results never
enter context.

```text
  tools                              code execution

  model ──call──> tool                model ──writes──> code
        <─result─                                        │
  model ──call──> tool                        host ──────┤ external function
        <─result─                                        │ (the only capability)
  model ──call──> tool                                   ▼
        <─result─                                   Precogly API
                                                         │
  every row through context           only the answer ───┘ through context
```

Two of the four collisions dissolve without touching Precogly at all.

The catalogs are unpaginated, so the whole of one is a single call: threat-library 21 rows
/ 19.8 KB, countermeasure-library 31 / 5.4 KB, component-library 5 / 1.5 KB,
taxonomy-entries 387 / 79.9 KB. About 107 KB for all four. Fetch the catalog into the
sandbox, filter it in code, and CWE-20 costs one request and returns nine rows — a question
that has no route through the API today.

That inverts what #208 was recorded as meaning. The deferral of catalog pagination went
into the notes as settled and harmless. Under a tool architecture it is a liability, since
an unbounded response is a projection problem. Under code execution it is the enabling
property, and it survives #99: full CWE, CAPEC, ATT&CK and ATLAS packs take
taxonomy-entries to roughly a megabyte, which is nothing in a sandbox and fatal in a
context window.

## The sandbox

Running model-written Python needs a boundary, and where the boundary sits decides what is
given up.

`pydantic-monty` puts it inside the language: a Python interpreter written in Rust, with
execution in worker subprocesses, where capability arrives only through external functions
the host registers and implements. Measured at 0.0.19 against the sandbox worker:

| available | gated | absent |
| --- | --- | --- |
| `datetime` incl. `fromisoformat` and `timedelta`, `json`, `re`, `math`, builtins, comprehensions, lambdas | `datetime.now` — a clock is a host resource | `collections`, `itertools`, `eval`, `__import__`, `dir`, `socket`, `subprocess` |

`os` imports but is a stub with no `system`, and `os.environ` raises. That last one is worth
stating plainly: `PRECOGLY_TOKEN` is unreachable from generated code even in principle.
`open` exists as a name but is permission-gated, so the announcement article's claim that it
"simply doesn't exist" describes the effect and not the mechanism.

The alternative puts the boundary around the process.
[Anthropic's sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
wraps `sandbox-exec` on macOS, bubblewrap with seccomp on Linux, and WFP on Windows (alpha),
with egress filtered by domain through HTTP and SOCKS5 proxies. It sandboxes arbitrary
processes, including MCP servers, and is not coupled to Claude — it wraps a command, so it
works identically under opencode driving a local model.

Monty is the cheaper first move, on one specific ground. Precogly runs on `localhost:8000`,
next to Postgres on `5432`, and loopback is where every process-level sandbox is weakest.
That is the substance of CVE-2026-25904, where `mcp-run-python`'s Deno sandbox was granted
loopback network permission and sandboxed code could reach services on the host — affecting
all versions to 0.0.22, with no fix available. Monty has no socket API, so there is no
network permission to misconfigure. The exposure is structural rather than managed.

That advantage expires. Under [0003](0003-oauth-authorization-server.md) Precogly becomes a
remote host and domain allowlisting is clean, at which point the two compose: a restricted
interpreter that cannot open a socket, inside a process that could not route anywhere but
Precogly if it did.

## What a model actually writes

Snippets written by someone who knows the constraints prove nothing. So gpt-oss-20b was
given the host functions and the four questions through LM Studio, and its output was fed
to Monty unmodified.

| prompt | reached for | outcome |
| --- | --- | --- |
| host functions only | `datetime` | crashed on `datetime.now`; the import itself was fine |
| host functions + the subset rules | nothing | ran clean, and **invented a constant for today's date** |
| host functions + a host `now()` | `datetime`, `collections` | used `now()` correctly; crashed on `collections` |

Where they ran, the answers were correct and matched the hand-written versions exactly.

The result that matters is the middle row. Told what it could not use, the model wrote
`threshold_date = "2026-06-30"` with a comment assuming today's date, and returned a
confident answer resting on a guess. The unconstrained runs failed loudly, and
`ModuleNotFoundError: No module named 'collections'` is a precise signal an agent can act
on and retry against.

So the subset is not documented to the model. Gaps are surfaced as errors and fed back;
genuinely gated capabilities like the clock are supplied as host functions. Constraining the
prompt trades a good failure for a bad one.

The two modules a naive model reached for, `collections` and `itertools`, are both
hand-rollable, and the model hand-rolled the counter itself when it did not import one.

## Corrections

Two things recorded earlier were wrong, both in the direction of making the API look worse
than it is.

**"Which models map to SOC 2" never needed a call per model**, and the reason 0002 gave for
dropping the field does not hold — the three queries per row are the server's, paid on every
listing request, because `frameworks` is a `SerializerMethodField` in the list serializer's
`fields`. The projection only ever controlled tokens. Corrected in 0002, and the field is
now carried as names.

**The CWE-20 row count depends on the matcher.** Exact match gives 9 threats; `icontains`
gives 17, because it also matches CWE-200 and CWE-201. DRF's `SearchFilter` uses `icontains`,
so 17 is what adding those fields to `search_fields` would return — and over-matching on
identifiers is a wart worth naming when that is raised upstream.

## When to revisit

Not on a date. Two triggers, either of which is enough:

- **The tool count reaches nine.** Six are planned and the measured degradation starts
  around ten, so the ninth is the last comfortable one. Counting is the check.
- **A question arrives that hand-written filtering cannot serve.** An aggregate rather than
  a predicate — a distribution, a ranking across models, a count grouped by something.
  Filters do not produce these and no upstream fix will.

Neither has fired. Six tools with client-side filtering, the parameters that already exist,
and an audit of every projection for the mistake 0002 made will carry further than the first
draft of this document assumed.

## Trade-offs

- **`pydantic-monty` is 0.0.19 and labelled experimental**, and its published API no longer
  matches its announcement — the constructor and `run()` described there do not exist, and
  the current shape was only found by reading the type stubs. Depending on it means pinning
  hard and expecting breakage. Accepted because the alternative is a Node dependency in a
  Python project, and because nothing here is on the critical path yet.
- **The whole-catalog fetch is a bet on catalogs staying small.** 107 KB today, roughly a
  megabyte after #99. It stops being free somewhere past that, and the fallback is the
  server-side filters this document argues against building one at a time.
- **Sandboxing is not authorization.** Generated code reaches whatever the host functions
  reach, which is whatever the caller's token reaches. [0001](0001-service-token-model.md)
  still carries the entire access-control story, and a sandbox that blocks `os.environ` has
  done nothing about a token that can read another organization's data.
- **Six tools is inside the budget**, and three of the four cases that motivated this
  document turned out not to need it. Someone reading this later should treat the direction
  as sound and the urgency as unproven, and check the triggers above before acting on it.
  The measurements here — the sandbox probes, the catalog sizes, the model runs — are worth
  more than the argument they were gathered for.
- **The probes are not in the repository.** `tmp/sandbox_snippets.py` and
  `tmp/monty_model_probe.py` produce every measurement above and are gitignored, so a fresh
  clone cannot reproduce any of it — the same problem as the second-organization fixture,
  and the same fix.
