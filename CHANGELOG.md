# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versions follow
SemVer.

## [0.1.0]

First release. The full five-act affect logic, packaged as an importable
Python library with an optional MCP server — landed as one release, all
five acts at once, with no partial "steward-only" cut.

### Added

- **`core/` affect logic**, carried over verbatim from the AstrBot plugin:
  `primal` (deterministic lexicon selection and pool shrinkage), `arbiter`
  (seven-verdict decision table, finitude-modulated swallow thresholds),
  `intrinsic` (proactive-speech decision + dream ticking), `shadow` (concern
  signal extraction, closed output whitelist), `finitude` (monotonic
  plasticity aging, epoch transitions, anthology assembly), `binding`
  (per-session record store). Zero `astrbot`/`sylanne_core`/`random` imports
  in this layer, enforced by an AST-scanning structure test.
- `engine_bridge.py`: the sole `sylanne-core` integration point, carried
  over with the framework-specific plugin identifier swapped in.
- **Delegation model**: `affect_arbitrate` lets an agent submit a draft
  reply for a verdict (`PASS`/`TRIM`/`SWALLOW`/`REPLACE`) and returns
  `final_text` to send instead — the MCP replacement for the AstrBot
  plugin's silent pipeline interception.
- **Outbox**: a per-session due/expiry queue that buffers every line Yelos
  would otherwise emit unprompted (delayed withdrawals, proactive
  check-ins, dream murmurs, concern nudges, epoch notices), drained only by
  `affect_impulse` — the single delivery mechanism for a protocol with no
  server-initiated push.
- **Background heartbeat** generating proactive/dream/concern candidates
  into the outbox on an interval, with an `impulse`-inline fallback when
  disabled, and a soft session cap for hosts serving many relationships at
  once.
- **Two-stage confirmation for `affect_farewell`**: an irreversible seal
  requires a first call to obtain a token and life summary, then a second
  call with that token to actually seal and export — a server-side guardrail
  independent of client UI.
- **Independent per-process `data_dir`** with a startup process lock,
  refusing a second process against the same directory; an explicit opt-in
  `engine_data_dir` for deliberately sharing one heart with another
  `sylanne-core` host.
- **`plasticity.ledger`**: an append-only, crash-resistant record of every
  plasticity decrease, keyed by a monotonic per-session incarnation
  counter (not wall-clock seconds) so that a same-second rebirth can never
  be merged with the previous life's aging.
- Full v0.1 tool set: `affect_submit`, `affect_state`, `affect_guidance`,
  `affect_tick`, `affect_arbitrate`, `affect_impulse`, `affect_bind`,
  `affect_pause`, `affect_reset`, `affect_farewell`; resources
  (`affect://state`, `affect://guidance`, `affect://anthology`); prompts
  (`yelos_contract`, `yelos_companion_setup`).
- Runs fully with no LLM configured (local rule-based degraded evaluation);
  optional OpenAI-compatible `assessor_model` for improved precision.
- `steward` (default, read-only tone guidance, never withholds or delays a
  reply) and `companion` (explicit opt-in, full five-act dynamics including
  aging) modes.
- 131 migrated core-layer tests plus a new MCP-layer suite covering the
  outbox, guidance mapping, arbitration flow, submit flow, heartbeat/impulse
  concurrency, persistence, sovereignty, and server contract.

### Known limitations (documented, not silently accepted)

- Dream murmurs require the server process to stay alive overnight to
  accumulate ticks; under `stdio` transport this makes them near-unusable
  unless the client session is left open all night. Only a
  `streamable-http` daemon makes them reliably real.
- `speaker` on `affect_submit` is a self-reported string the server cannot
  independently verify — a new trust boundary relative to the AstrBot
  version, which had framework-guaranteed turn direction.
- v0.1 assumes one `session_id` per stable relationship; it is not designed
  for a single agent serving a large, churning population of end users.
- Cross-host shared hearts, multi-client session routing, and MCP-sampling
  as an assessor source are deferred to v0.2.

### Removed (relative to the AstrBot plugin)

- The three AstrBot-pipeline-specific patches (streaming guard, hook
  priority, `stop_event` propagation) — none have an MCP equivalent, since
  MCP has no message pipeline, hook priority system, or yield/event chain.
  The lesson behind the streaming guard (issue26: non-plain content
  swallowed whole) is preserved as a contract in `affect_arbitrate`'s tool
  description instead: only pass the text portion of a reply to arbitration.
- Message-recall performance (`primal_revoke_enabled`) — an aiocqhttp
  platform feature with no "recall an already-sent message" concept in MCP.
- The AstrBot `Star` plugin shell, its three mount points, and its command
  group — replaced by MCP tool/resource/prompt registration and server
  lifespan management.
