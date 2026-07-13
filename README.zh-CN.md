# Yelos

[English](README.md) · **中文**

![license](https://img.shields.io/badge/license-AGPL--3.0-blue)
![status](https://img.shields.io/badge/status-technical%20reserve%20%C2%B7%20v0.1-orange)
![python](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![tests](https://img.shields.io/badge/tests-1251%20passing-brightgreen)

**面向宿主对话轮循环的情感状态跟踪与输出仲裁，一个可导入的 Python 库。**

> **⚠️ 技术储备 / Technical reserve —— 研究原型，按现状提供（as-is）。**
> 它是作为一项能力被构建并封存下来的，而不是一个可直接上生产的、经过打磨的发布版。它端到端可运行——可安装、1250+ 测试全绿、有操作系统级的进程锁——但仍带有 v0.1 的范围限制（在本 README 与路线图中如实记录）、一些粗糙的边角，并且**不提供任何支持或稳定性保证。** 把它当作一个起点来用，而不是一个成品。
> AGPL-3.0-or-later。

## 这是什么

Yelos 是一个用 Python 实现的库，把五个阶段（"五幕"）的情感驱动表达逻辑封装起来，构建在 [`sylanne-core`] 情感引擎 SDK 之上。你可以把它直接 `import` 进宿主应用——一个 agent 运行时、一个桌面陪伴软件，或任何已经拥有自己对话轮次循环、只想要情感/仲裁逻辑的地方。它的工程形态是：

- `yelos.session.SessionManager` —— 编排层。持有 time/config/engine/persistence，并按顺序驱动五幕。这是这个库真正的入口点；其余一切都挂在它上面。
- `yelos.core` —— 冻结的、零依赖的 v0.1 纯逻辑基线（`sget`/`split_sentences`，以及 `arbiter.arbitrate`、`primal.LexiconProvider`、`intrinsic.decide`、`shadow.extract_concern`、`finitude.settle_day` / `epoch_transition`、`binding.BindingStore`）。下面每一个深化模块都包裹或回退到这一层——当那些可选系统关闭、构造失败或抛出异常时，仍在运行的就是它。
- `yelos.primal` —— 第一幕/第二幕的话语生成（词库、构词、韵律、白名单闸门）。`build_composer(cfg, p_lookup, lang_lookup, incarnation_lookup) -> Composer`，其 `.compose(...)` 返回一个 `Utterance`。通过 `primal_composer_enabled` 选择性开启；默认路径是冻结的 `core.primal.LexiconProvider`。
- `yelos.arbiter` —— 第二幕仲裁的深化（守卫链、策略注册表、调制曲线、滞回）。`build_pipeline(policy_id, theta, curve, duel_writer)` 以及 `POLICY_REGISTRY`。通过 `arbiter_pipeline_enabled` 选择性开启；默认路径是 `core.arbiter.arbitrate`。
- `yelos.intrinsic` —— 第三幕的主动发言/梦境场动力学。`build_intrinsic(cfg_dict) -> IntrinsicSystem`，`GATE_CHAIN`。通过 `intrinsic_field_enabled` 选择性开启；默认路径是 `core.intrinsic.decide`。
- `yelos.shadow` —— 第四幕的心智理论（theory-of-mind）关切建模（一种模拟理论式的近似，不是读心，输出是封闭白名单）。`build_shadow_system(cfg, bridge, memory_facade=..., data_dir=..., detector_set=...) -> ShadowSystem`。通过 `shadow_orchestrator_enabled` 选择性开启；默认路径是 `core.shadow.extract_concern`。
- `yelos.finitude` —— 第五幕的可塑性/衰老/告别。`build_settle_fn(record, sid, ledger=..., ledger_ext=..., config=..., data_dir=...)` 产出供 `core.binding.BindingStore.rollover` 消费的闭包。通过 `finitude_settle_enabled` 选择性开启；默认路径是 `core.finitude.settle_day`。
- `yelos.memory` —— 跨会话回忆器官（L1 情景 / L2 语义 / L3 自传体）。公开接口是 `MemoryFacade`，以及 `yelos.memory.contracts` 里的 dataclass（`EpisodeEvent`、`RecallQuery` 等）。`MemoryFacade(root, memory_config).observe(sid, gen, EpisodeEvent)` 与 `.affect_recall_view(...)`。
- `yelos.engine_bridge.EngineBridge` —— 全库唯一 import `sylanne_core` 的地方；有防护，它缺失时会降级为返回 `None`/`False`，而不是抛出异常。

每一个可选的深化模块（`primal`/`arbiter`/`intrinsic`/`shadow`/`finitude` 中超出冻结核心的那部分组合逻辑）都**默认关闭**，并且在构造或运行时出错时会安全回退——某条深化路径失败，绝不会让库停止产出输出。

## 依赖要求

- Python >= 3.10
- `sylanne-core`（情感引擎 SDK）。没有它，`SessionManager` 依然能工作，每个方法依然会给出回应——引擎会回退到本地基于规则的评估（`degraded` 模式）。它是硬性的 *package* 依赖（在 `pyproject.toml` 中声明），但对"给出回应"这件事来说，并不是硬性的 *runtime* 依赖。
- 给库使用者的提醒：`pip install yelos` 也会一并拉入 `mcp`、`anyio`、`starlette`，即使你完全不碰 MCP 接口——这个包目前还没有拆分出 extras，所以无论你是直接用 `yelos.session`，还是把它当服务器来跑，这些依赖都会落进你的依赖树里。

## 作为库来使用

像安装任何其他包一样安装它：

```bash
uv add yelos
# or: pip install yelos
```

编排层是 `SessionManager`；`yelos.server.build_manager` 是一个便捷构造函数，它会同步地把 config + `EngineBridge` 接好线，并加载已持久化的 bindings——使用它（或者自己组装各个部件），全程都不需要碰 FastMCP：

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

`SessionManager` 基于 asyncio（每个会话一把 `asyncio.Lock`，可以安全地在一个宿主进程里同时服务多个并发会话），但不依赖 MCP transport、FastMCP，也不依赖一个正在运行的服务器——一个拥有自己的 stdio/JSON-RPC 循环（或任何其他对话轮次循环）的宿主，可以直接从自己的事件循环里调用这些方法。`manager.pause`、`manager.reset` 和 `manager.farewell` 是用户主权（user-sovereignty）动作（farewell 是两阶段的、不可逆——token 握手的细节见 `yelos.sovereignty`）。

配置来自工作目录下的 `yelos.config.json`（或 `$YELOS_CONFIG`）加上环境变量；优先级是文件值 > 环境变量 > 默认值（完整的键表见 `src/yelos/config.py`——data_dir、heartbeat、quiet hours、finitude、assessor_model，以及各深化模块的开关标志）。配置键在各个版本之间只会增加，不会被删除或挪作他用。

### 一个 `data_dir`，一个进程

Yelos 默认使用一个**独立的、按进程划分的 `data_dir`**（`~/.yelos`，或 `$YELOS_DATA_DIR`）——而不是引擎 SDK 共享的数据目录，因为那个保证只在*单一进程内*成立。两个进程（或者两个指向同一目录的进程内 `SessionManager`）会互相双写覆盖，悄悄丢失对方的更新。一把进程锁（`data_dir/yelos.lock`）强制执行这一点；不要绕开它。如果你确实想在同一台机器上，和另一个基于 `sylanne-core` 的宿主共用同一颗心，把 `engine_data_dir` 设为那个宿主共享的数据目录——这是一个显式选择加入的逃生舱口，单写者保证由你自己负责。

### 模式：steward 与 companion

| | `steward`（默认） | `companion`（选择性开启） |
|---|---|---|
| 她做什么 | 读取节奏/疲劳/温度信号，通过 `guidance()` 把它们转化为语气/温度上的*建议*。绝不触碰任务本身的长度或节奏。 | 完整动态：她可以改写/压下你的草稿、主动开口说话、受 shadow 信号影响，并且（默认情况下）会衰老。 |
| 仲裁 | 始终 `PASS`——你的草稿原样发出。 | 完整的七态判决表（`PASS`/`TRIM`/`SWALLOW`/`REPLACE` 等）。 |
| 主动发言 / 衰老 | 关闭。 | 默认开启；`finitude_enabled=false` 或 `lifespan_active_days=0` 会换来一个不会衰老的陪伴者。 |

`companion` 必须通过 `manager.bind(sid, mode="companion")` 显式开启——它绝不是隐含的默认值。在一个尚未绑定的会话上第一次调用 `submit()`，会惰性地创建一个无名的 `steward` 绑定，不需要任何仪式性的步骤。

### 主动发言是拉取式的——outbox

没有什么会凭自己的意愿主动推送。所有 Yelos 会在没被提示的情况下发出的话——在压力下咽下某句之后重新浮现的延迟话语、一次主动的问候、一句梦呓、一个关切的轻推、当表达范围明显收窄时的一次纪元通知——都被缓冲在按会话划分的 **outbox** 里，带着到期时间和过期时间，只有在宿主调用 `manager.impulse(sid)` 时才会被取出。如果某个工具/方法的返回值里带着 `pending > 0`，或者 `arbitrate()` 返回了非 `None` 的 `delayed`，那就是该尽快去轮询 `impulse()` 的信号。如果始终没有人来轮询，缓冲的话语会过期，并被悄悄丢弃。

### 不依赖 LLM 也能运行

产品实际运作的每一部分——话语生成、仲裁、finitude/衰老——都是确定性的，不需要任何 LLM 调用；只有引擎自身的语义评估器才会从 LLM 中受益。`build_assessor(None)`（未配置 `assessor_model` 时的默认值）会给你一个零配置的、基于规则的降级评估器。想要更精确的评估，可以在 `yelos.config.json` 里配置一个 OpenAI 兼容的 `assessor_model` 块（不需要额外的运行时依赖——纯标准库 HTTP）。

### 数据存放位置与清除方法

Yelos 自身的全部状态（bindings、可塑性台账、outbox 内容、导出的 anthology）都存放在 `data_dir` 下（默认 `~/.yelos`），与情感引擎存放自身会话状态的位置（`engine_data_dir`，默认 `{data_dir}/engine`）相互独立。除非你配置了 `assessor_model`，否则这里的一切都不会联网。要重置单个关系：用 `manager.reset(sid)`（保留 binding/名字），或者用 `manager.farewell(sid)`（永久封存它，可以先导出 anthology，需要两步 token 确认）。要清空一切：停掉进程，删除 `data_dir`。

## 可选：作为 MCP 服务器运行

上面这个库，也通过 [Model Context Protocol](https://modelcontextprotocol.io/) 对外暴露，供那些想把它当作一整套 MCP 工具来消费、而不是进程内 import 的宿主使用——`yelos.server.build_server` 把同一套 `SessionManager` 方法包装成了 11 个 FastMCP 工具（`affect_submit`、`affect_state`、`affect_guidance`、`affect_tick`、`affect_arbitrate`、`affect_impulse`、`affect_bind`、`affect_pause`、`affect_reset`、`affect_farewell`、`affect_recall`），外加 3 个资源（`affect://state/{session_id}`、`affect://guidance/{session_id}`、`affect://anthology/{session_id}`）和 2 个 prompt（`yelos_contract`、`yelos_companion_setup`）。

```bash
python -m yelos          # stdio transport (default)
YELOS_TRANSPORT=streamable-http python -m yelos   # long-running daemon
```

这种模式是为 MCP 原生宿主准备的（Claude Desktop、某个 IDE agent），它们会拉起一个 `stdio` 服务器，或者去连接一个 `streamable-http` 端点；使用五幕逻辑本身并不需要它——见上文"作为库来使用"。因为 MCP 没有服务器发起的推送，同样的拉取式 `outbox` / `impulse` 轮询模型在这里也适用。梦呓（dream murmur）在 `stdio` 下尤其近乎不可用：它们在夜间的静默窗口中武装待发，需要进程整夜存活来累积 tick，而生命周期绑定在客户端上的 `stdio` 会话通常做不到这一点。`session_id`（v0.1）是调用者提供的一个不透明字符串，没有跨客户端路由——支持的形态是每个 `session_id` 对应一个项目或一个客户端，而不是面向大规模用户群体的多租户路由器。

## 许可证

AGPL-3.0-or-later —— 详见 `LICENSE`。
