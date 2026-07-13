# Yelos

**English** · [中文](README.zh-CN.md)

![license](https://img.shields.io/badge/license-AGPL--3.0-blue)
![status](https://img.shields.io/badge/status-technical%20reserve%20%C2%B7%20v0.1-orange)
![python](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![tests](https://img.shields.io/badge/tests-1251%20passing-brightgreen)

**Affect-state tracking and output arbitration for a host's turn loop, as an importable Python library.**

> **⚠️ Technical reserve / 技术储备 — research prototype, provided as-is.**
> Built and banked as a capability, not a production-hardened release. It
> works end-to-end — installable, 1250+ tests green, an OS-level process
> lock — but it carries v0.1 scope limits (documented honestly throughout
> this README and the roadmap), rough edges, and **no support or stability
> guarantees.** Use it as a starting point, not a finished product.
> AGPL-3.0-or-later.

## What this is

Yelos is a Python library implementing five staged "acts" of
affect-driven expression logic, built on the [`sylanne-core`] affect
engine SDK. You `import` it directly into a host application — an agent
runtime, a desktop companion, anything that already owns its own turn loop
and wants the affect/arbitration logic. The engineering shape is:

- `yelos.session.SessionManager` — the orchestration layer. Holds
  time/config/engine/persistence and sequences the five acts. This is the
  actual library entry point; everything else hangs off it.
- `yelos.core` — the frozen, zero-dependency v0.1 pure-logic baseline
  (`sget`/`split_sentences` plus `arbiter.arbitrate`, `primal.LexiconProvider`,
  `intrinsic.decide`, `shadow.extract_concern`, `finitude.settle_day` /
  `epoch_transition`, `binding.BindingStore`). Every deepened module below
  wraps or falls back to this layer — it is what still runs if the opt-in
  systems are off, fail to construct, or throw.
- `yelos.primal` — Act I/II utterance composition (lexicon, morphology,
  prosody, whitelist gate). `build_composer(cfg, p_lookup, lang_lookup,
  incarnation_lookup) -> Composer`, whose `.compose(...)` returns an
  `Utterance`. Opt-in via `primal_composer_enabled`; default path is the
  frozen `core.primal.LexiconProvider`.
- `yelos.arbiter` — Act II arbitration deepening (guard chain, policy
  registry, modulation curves, hysteresis). `build_pipeline(policy_id,
  theta, curve, duel_writer)` plus `POLICY_REGISTRY`. Opt-in via
  `arbiter_pipeline_enabled`; default path is `core.arbiter.arbitrate`.
- `yelos.intrinsic` — Act III proactive-speech/dream field dynamics.
  `build_intrinsic(cfg_dict) -> IntrinsicSystem`, `GATE_CHAIN`. Opt-in via
  `intrinsic_field_enabled`; default path is `core.intrinsic.decide`.
- `yelos.shadow` — Act IV theory-of-mind concern modeling (simulation-theory
  approximation, not mind-reading, closed whitelist output).
  `build_shadow_system(cfg, bridge, memory_facade=..., data_dir=...,
  detector_set=...) -> ShadowSystem`. Opt-in via
  `shadow_orchestrator_enabled`; default path is `core.shadow.extract_concern`.
- `yelos.finitude` — Act V plasticity/aging/farewell. `build_settle_fn(record,
  sid, ledger=..., ledger_ext=..., config=..., data_dir=...)` produces the
  closure consumed by `core.binding.BindingStore.rollover`. Opt-in via
  `finitude_settle_enabled`; default path is `core.finitude.settle_day`.
- `yelos.memory` — cross-session recall organ (L1 episodic / L2 semantic /
  L3 autobiographical). Public surface is `MemoryFacade` plus the
  dataclasses in `yelos.memory.contracts` (`EpisodeEvent`, `RecallQuery`,
  etc.). `MemoryFacade(root, memory_config).observe(sid, gen, EpisodeEvent)`
  and `.affect_recall_view(...)`.
- `yelos.engine_bridge.EngineBridge` — the sole place `sylanne_core` is
  imported; guarded so its absence degrades to `None`/`False` returns
  instead of raising.

Every opt-in deepened module (`primal`/`arbiter`/`intrinsic`/`shadow`/
`finitude` composition beyond the frozen core) is **off by default** and
falls back safely on any construction or runtime error — a failed deepened
path never stops the library from producing output.

## Requirements

- Python >= 3.10
- `sylanne-core` (the affect engine SDK). Without it, `SessionManager`
  still works and every method still answers — the engine falls back to
  local rule-based evaluation (`degraded` mode). It is a hard *package*
  dependency (declared in `pyproject.toml`), just not a hard *runtime*
  dependency for getting an answer.
- Note for library consumers: `pip install yelos` also pulls in `mcp`,
  `anyio`, and `starlette` even if you never touch the MCP surface — the
  package isn't currently split into extras, so those land in your
  dependency tree regardless of whether you use `yelos.session` directly
  or run it as a server.

## Using it as a library

Install it like any other package:

```bash
uv add yelos
# or: pip install yelos
```

The orchestration layer is `SessionManager`; `yelos.server.build_manager`
is a convenience constructor that wires config + `EngineBridge` + loads
persisted bindings synchronously — use it (or build the pieces yourself)
without ever touching FastMCP:

```python
from yelos.config import load as load_config
from yelos.server import build_manager, build_assessor

config = load_config()                 # yelos.config.json / env / defaults
manager = build_manager(config)        # sync: SessionManager + EngineBridge, bindings loaded

await manager.ensure_engine()          # attach sylanne-core (or run degraded if absent)

sid = "some-session-id"
await manager.bind(sid, name="", mode="companion")   # explicit opt-in to full dynamics
await manager.submit(sid, user_text, speaker="user")  # Act I: feed a real user turn
verdict = await manager.arbitrate(sid, draft_reply)   # Act II: PASS/TRIM/SWALLOW/REPLACE
send_this = verdict["final_text"]                     # empty string on SWALLOW = silence
collected = await manager.impulse(sid)                # Act III: drain due proactive/dream/concern lines
snapshot = await manager.state(sid)                   # read-only 8-dim affect snapshot
hints = await manager.guidance(sid)                   # tone/length/pace suggestions, never commands
```

`SessionManager` is asyncio-based (per-session `asyncio.Lock`, safe for one
host process serving multiple concurrent sessions) but has no dependency on
MCP transport, FastMCP, or a running server — a host with its own
stdio/JSON-RPC loop (or any other turn loop) can call these methods
directly from its own event loop. `manager.pause`, `manager.reset`, and
`manager.farewell` are the user-sovereignty actions (farewell is two-stage
and irreversible — see `yelos.sovereignty` for the token handshake).

Configuration is `yelos.config.json` in the working directory (or
`$YELOS_CONFIG`) plus environment variables; file values win, then env,
then defaults (see `src/yelos/config.py` for the full key table — data_dir,
heartbeat, quiet hours, finitude, assessor_model, and the deepened-module
opt-in flags). Config keys only ever get added, never removed or
repurposed, across releases.

### One `data_dir`, one process

Yelos defaults to an **independent, per-process `data_dir`** (`~/.yelos`,
or `$YELOS_DATA_DIR`) — not the engine SDK's shared data directory, because
that guarantee only holds *within one process*. Two processes (or two
in-process `SessionManager`s pointed at the same directory) will double-flush
and silently lose updates to each other. A process lock
(`data_dir/yelos.lock`) enforces this; don't route around it. If you
deliberately want to share one heart with another `sylanne-core`-based
host on the same machine, set `engine_data_dir` to that host's shared data
directory — an explicit opt-in escape hatch, and you own the single-writer
guarantee.

### Modes: steward vs. companion

| | `steward` (default) | `companion` (opt-in) |
|---|---|---|
| What she does | Reads rhythm/fatigue/warmth signals and turns them into tone/warmth *suggestions* via `guidance()`. Never touches task length/pacing. | Full dynamics: she can rewrite/withhold your draft, speak on her own, be affected by shadow signals, and (by default) age. |
| Arbitration | Always `PASS` — your draft goes out unchanged. | Full seven-verdict decision table (`PASS`/`TRIM`/`SWALLOW`/`REPLACE`, etc.). |
| Proactive speech / aging | Off. | On by default; `finitude_enabled=false` or `lifespan_active_days=0` gives a non-aging companion instead. |

`companion` must be turned on explicitly via `manager.bind(sid,
mode="companion")` — it is never the implicit default. First `submit()` on
an unbound session lazily creates a nameless `steward` binding with no
ceremony required.

### Proactive speech is pull-based — the outbox

Nothing pushes on its own initiative. Everything she would say
unprompted — a delayed line re-surfaced after a pressured swallow, a
proactive check-in, a dream murmur, a concern nudge, an epoch notice when
expressive range narrows — is buffered in a
per-session **outbox** with a due time and an expiry, and is only surfaced
when the host calls `manager.impulse(sid)`. If a tool/method response
carries `pending > 0`, or `arbitrate()` returns `delayed != None`, that's
the cue to poll `impulse()` soon. If nothing ever polls, buffered lines
expire and are quietly dropped.

### Running with no LLM

Every piece of the actual product — utterances, arbitration,
finitude/aging — is deterministic and needs zero LLM calls; only the
engine's own semantic assessor benefits from one. `build_assessor(None)`
(the default when no `assessor_model` is configured) gives you a degraded
rule-based evaluator with zero setup. Configure an OpenAI-compatible
`assessor_model` block in `yelos.config.json` for better assessment
precision (zero extra runtime dependencies — plain stdlib HTTP).

### Data location and how to clear it

All of Yelos's own state (bindings, plasticity ledger, outbox contents,
exported anthologies) lives under `data_dir` (default `~/.yelos`), separate
from wherever the affect engine keeps its own session state
(`engine_data_dir`, default `{data_dir}/engine`). Nothing here talks to the
network unless you configure `assessor_model`. To reset a single
relationship: `manager.reset(sid)` (keeps the binding/name) or
`manager.farewell(sid)` (permanently seals it, optionally exporting the
anthology first, two-step token-confirmed). To erase everything: stop the
process and delete `data_dir`.

## Optional: run as an MCP server

The library above is also exposed over the [Model Context Protocol]
(https://modelcontextprotocol.io/) for hosts that want to consume it as an
MCP tool set rather than an in-process import — `yelos.server.build_server`
wraps the same `SessionManager` methods in 11 FastMCP tools
(`affect_submit`, `affect_state`, `affect_guidance`, `affect_tick`,
`affect_arbitrate`, `affect_impulse`, `affect_bind`, `affect_pause`,
`affect_reset`, `affect_farewell`, `affect_recall`) plus 3 resources
(`affect://state/{session_id}`, `affect://guidance/{session_id}`,
`affect://anthology/{session_id}`) and 2 prompts (`yelos_contract`,
`yelos_companion_setup`).

```bash
python -m yelos          # stdio transport (default)
YELOS_TRANSPORT=streamable-http python -m yelos   # long-running daemon
```

This mode exists for MCP-native hosts (Claude Desktop, an IDE agent) that
spawn a `stdio` server or reach a `streamable-http` endpoint; it is not
required to use the five-act logic — see "Using it as a library" above.
Because MCP has no server-initiated push, the same pull-based `outbox` /
`impulse` polling model applies here too. Dream murmurs in particular are
near-unusable under `stdio`: they arm during a nightly quiet window and
need the process alive overnight to accumulate ticks, which a `stdio`
session tied to a client's lifetime typically isn't. `session_id` (v0.1) is
an opaque string the caller provides with no cross-client routing — one
project or client per `session_id` is the supported shape, not a
large-population multi-tenant router.

## License

AGPL-3.0-or-later — see `LICENSE`.
