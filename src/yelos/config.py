"""配置模型(蓝图 §6.5/§7.3)——env + 可选 yelos.config.json 装配。

YelosConfig 是 server 级全局配置(mode 是 per-session、存 binding、不在此)。
只增不删:新配置键往表里加,不改旧键语义(§7.3)。纯标准库,零 astrbot /
零 sylanne_core / 零 core 依赖——config 只负责"读什么、解析成什么",
data_dir 的进程锁 / ledger 落盘归 persistence 层(§6.1/§7.4)。

**优先级 [疑义记录]**:§6.1 明列 `config.data_dir > $YELOS_DATA_DIR > ~/.yelos`
(文件值高于 env);§7.3 表又给每键标了 env。二者对 data_dir 的相对次序冲突。
本实现照 §6.1 的显式次序,对全部有 env 映射的键统一采「文件值 > 环境变量 >
默认」——文件是显式配置、应压过环境,与 §6.1 旗舰键一致、可预测。已记入返回疑义。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# --- 默认值(与 §7.3 表逐格对齐)---------------------------------------

DEFAULT_DATA_DIR = "~/.yelos"
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8760
DEFAULT_MODE = "steward"
DEFAULT_ARBITER_MIN_GAP_SECONDS = 180
DEFAULT_INTRINSIC_INTERVAL_SECONDS = 60
DEFAULT_INTRINSIC_DAILY_CAP = 3
DEFAULT_QUIET_HOURS = "01:00-08:00"
DEFAULT_LIFESPAN_ACTIVE_DAYS = 545
DEFAULT_HEARTBEAT_MAX_SESSIONS = 200
DEFAULT_FAREWELL_TOKEN_TTL_SECONDS = 600  # §3.6.3 两段式确认 token 时效 10min

# --- WebUI 门面键(接线波 §4;默认 ui_enabled=False → server 现状字节等价)----
DEFAULT_UI_ENABLED = False
DEFAULT_UI_TOKEN = ""  # 空 = 启动时随机生成(mount() 侧),不在 config 层造随机数
DEFAULT_UI_PORT = 0  # 0 = 未显式配置,由 resolved_ui_port() 派生(见下)
DEFAULT_UI_PORT_STDIO_FALLBACK = 8761  # stdio 辅助面无显式端口时的默认值
DEFAULT_UI_FEED_FULL_TEXT = False

# --- 深化模块键默认值(接线波 §2.4;默认取"与 v0.1 行为兼容"档)-----------
# 每个默认值都镜像该模块 config_defaults.py 里的 DEFAULT_*,并遵守
# INTEGRATION_SPEC "默认不改变现有可观测行为"(θ≡0/table/legacy/K=1/linear)。
# 注册进 YelosConfig 只是让这些键"可配置开启";是否真正路由由 session/server
# 层的 opt-in 旗标决定,默认路径仍走 v0.1 core。
DEFAULT_LANG = "zh"  # primal A7 一生一语 / guidance 句库语言
DEFAULT_GUIDANCE_PROFILE = "chat"  # guidance_BLUEPRINT §5.2:chat = v0.1 行为
# primal
DEFAULT_PRIMAL_LEXICON_PROFILE = "expanded"
DEFAULT_PRIMAL_CLOSURE_MAX = 4096
# intrinsic
DEFAULT_INTRINSIC_POLICY = "threshold"
DEFAULT_INTRINSIC_INTEGRATOR = "euler"
DEFAULT_DREAM_GENERATOR = "residue"
DEFAULT_MAX_CATCHUP_STEPS = 240
# arbiter
DEFAULT_ARBITER_POLICY = "table"  # table + θ≡0 = v0.1 逐字节兼容
# shadow
DEFAULT_SHADOW_DETECTOR_SET = "legacy"  # legacy = v0.1 逐字节兼容
DEFAULT_SHADOW_HYPOTHESES = 1  # K=1 = 单假设(不走 ensemble)
DEFAULT_SHADOW_INTENSITY_FN = "linear"
DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT = 4
DEFAULT_SHADOW_CALIBRATION_WINDOW = 60
# finitude
DEFAULT_FINITUDE_MODEL = "linear"  # linear = 委托 core.finitude.settle_day
DEFAULT_FINITUDE_MODEL_PARAMS = "{}"
DEFAULT_FINITUDE_EPOCH_TRACK = "fixed"
# distill(opt-in,默认关)
DEFAULT_DISTILL_ENABLED = False
DEFAULT_DISTILL_MODEL_DIR = "~/.yelos/models/distill"
DEFAULT_DISTILL_TIER = "ngram"
DEFAULT_DISTILL_BUDGET_MS = 50
DEFAULT_DISTILL_K_CANDIDATES = 8
DEFAULT_DISTILL_RERANKER = "hash"
# evolution(opt-in,默认关)
DEFAULT_EVOLUTION_ENABLED = False
DEFAULT_EVOLUTION_VELOCITY_BOUND = 0.05
DEFAULT_EVOLUTION_MIN_DAYS = 7
DEFAULT_EVOLUTION_ONLINE_WEIGHT = 0.0
DEFAULT_EVOLUTION_STRATEGY = "pattern_search"

_VALID_TRANSPORTS = ("stdio", "streamable-http")
_VALID_MODES = ("steward", "companion")
_QUIET_FALLBACK = (60, 480)  # 01:00-08:00 分钟区间

_CONFIG_FILENAME = "yelos.config.json"
_SYLANNE_CONFIG_FILENAME = "sylanne.config.json"


# --- assessor_model 块(§6.5/§7.5)-------------------------------------


@dataclass(frozen=True)
class AssessorModel:
    """OpenAI 兼容 assessor 配置。api_key 支持 ${ENV} 展开(勿提交密钥)。"""

    api_base: str
    api_key: str
    model: str


# --- 主配置 -------------------------------------------------------------


@dataclass(frozen=True)
class YelosConfig:
    """server 级全局配置。不可变;从 load() 装配。"""

    data_dir: str = DEFAULT_DATA_DIR
    engine_data_dir: str = ""
    transport: str = DEFAULT_TRANSPORT
    http_host: str = DEFAULT_HTTP_HOST
    http_port: int = DEFAULT_HTTP_PORT
    default_mode: str = DEFAULT_MODE
    assessor_model: AssessorModel | None = None
    arbiter_min_gap_seconds: int = DEFAULT_ARBITER_MIN_GAP_SECONDS
    express_trim_enabled: bool = True
    heartbeat_enabled: bool = True
    intrinsic_interval_seconds: int = DEFAULT_INTRINSIC_INTERVAL_SECONDS
    intrinsic_daily_cap: int = DEFAULT_INTRINSIC_DAILY_CAP
    quiet_hours: str = DEFAULT_QUIET_HOURS
    dream_murmur_enabled: bool = True
    shadow_enabled: bool = True
    finitude_enabled: bool = True
    lifespan_active_days: int = DEFAULT_LIFESPAN_ACTIVE_DAYS
    heartbeat_max_sessions: int = DEFAULT_HEARTBEAT_MAX_SESSIONS
    farewell_token_ttl_seconds: int = DEFAULT_FAREWELL_TOKEN_TTL_SECONDS

    # -- WebUI 门面键(接线波 §4;§5.5 只增不删,四键当前全缺,现在补上)------
    ui_enabled: bool = DEFAULT_UI_ENABLED
    ui_token: str = DEFAULT_UI_TOKEN
    ui_port: int = DEFAULT_UI_PORT
    ui_feed_full_text: bool = DEFAULT_UI_FEED_FULL_TEXT
    #: ``load()`` 实际读取的 yelos.config.json 路径(供 ``ui_config_overlay_
    #: path()`` 精确回写同一个文件);空串 = 直接构造(非经 ``load()``),
    #: 此时回退 env/默认文件名解析(与 ``load()`` 内部逻辑保持一致)。
    config_source_path: str = ""

    # -- 深化模块键(接线波 §2.4;默认 v0.1 兼容,routing 由 opt-in 旗标决定)--
    lang: str = DEFAULT_LANG
    # guidance
    guidance_profile: str = DEFAULT_GUIDANCE_PROFILE
    guidance_lang: str = DEFAULT_LANG
    # primal(deepened composer opt-in;默认仍走 core LexiconProvider)
    primal_composer_enabled: bool = False
    primal_lexicon_profile: str = DEFAULT_PRIMAL_LEXICON_PROFILE
    primal_template_enabled: bool = True
    primal_markov_enabled: bool = True
    primal_markov_min_corpus: int = 50
    primal_closure_max: int = DEFAULT_PRIMAL_CLOSURE_MAX
    primal_routes: str = ""
    # intrinsic(deepened field/scheduler opt-in;默认仍走 core.intrinsic.decide)
    intrinsic_field_enabled: bool = False
    intrinsic_policy: str = DEFAULT_INTRINSIC_POLICY
    intrinsic_integrator: str = DEFAULT_INTRINSIC_INTEGRATOR
    intrinsic_field_params: str = "{}"
    dream_generator: str = DEFAULT_DREAM_GENERATOR
    moments_enabled: bool = True
    max_catchup_steps: int = DEFAULT_MAX_CATCHUP_STEPS
    # arbiter(deepened pipeline opt-in;默认仍走 core.arbiter.arbitrate)
    arbiter_pipeline_enabled: bool = False
    arbiter_policy: str = DEFAULT_ARBITER_POLICY
    # shadow(deepened orchestrator opt-in;默认仍走 core.shadow.extract_concern)
    shadow_orchestrator_enabled: bool = False
    shadow_detector_set: str = DEFAULT_SHADOW_DETECTOR_SET
    shadow_hypotheses: int = DEFAULT_SHADOW_HYPOTHESES
    shadow_intensity_fn: str = DEFAULT_SHADOW_INTENSITY_FN
    shadow_engine_calls_per_beat: int = DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT
    shadow_calibration_window: int = DEFAULT_SHADOW_CALIBRATION_WINDOW
    # finitude(deepened settle_fn opt-in;默认仍走 core.finitude.settle_day)
    finitude_settle_enabled: bool = False
    finitude_model: str = DEFAULT_FINITUDE_MODEL
    finitude_model_params: str = DEFAULT_FINITUDE_MODEL_PARAMS
    finitude_epoch_track: str = DEFAULT_FINITUDE_EPOCH_TRACK
    # memory(供血面;默认开,affect_recall 与双写走 facade)
    memory_enabled: bool = True
    memory_block: dict = field(default_factory=dict)
    # distill / evolution(opt-in extras,默认关)
    distill_enabled: bool = DEFAULT_DISTILL_ENABLED
    distill_model_dir: str = DEFAULT_DISTILL_MODEL_DIR
    distill_tier: str = DEFAULT_DISTILL_TIER
    distill_budget_ms: int = DEFAULT_DISTILL_BUDGET_MS
    distill_k_candidates: int = DEFAULT_DISTILL_K_CANDIDATES
    distill_reranker: str = DEFAULT_DISTILL_RERANKER
    evolution_enabled: bool = DEFAULT_EVOLUTION_ENABLED
    evolution_velocity_bound: float = DEFAULT_EVOLUTION_VELOCITY_BOUND
    evolution_min_days: int = DEFAULT_EVOLUTION_MIN_DAYS
    evolution_online_weight: float = DEFAULT_EVOLUTION_ONLINE_WEIGHT
    evolution_strategy: str = DEFAULT_EVOLUTION_STRATEGY

    # -- 派生:data_dir 解析(§6.1)---------------------------------------

    def resolved_data_dir(self) -> Path:
        """Yelos 自己的 data_dir(独立)。~ 展开为绝对路径。

        不创建目录、不加锁——那是 persistence 层的事(§6.1)。
        """
        return Path(os.path.expanduser(self.data_dir)).resolve()

    def resolved_engine_data_dir(self) -> Path:
        """引擎数据目录:engine_data_dir 空 → {data_dir}/engine;否则该路径。

        填 shared_data_dir() 路径 = 共心(opt-in,用户自保单进程,§1.1/§6.1)。
        """
        if self.engine_data_dir.strip():
            return Path(os.path.expanduser(self.engine_data_dir)).resolve()
        return self.resolved_data_dir() / "engine"

    def lock_path(self) -> Path:
        """进程锁文件路径(persistence 层写 PID;§6.1)。"""
        return self.resolved_data_dir() / "yelos.lock"

    def ledger_path(self) -> Path:
        """plasticity.ledger 路径(persistence 层追加写;§7.4)。"""
        return self.resolved_data_dir() / "plasticity.ledger"

    def bindings_path(self) -> Path:
        """bindings.json 路径(binding 层原子写;§1.2)。"""
        return self.resolved_data_dir() / "bindings.json"

    def anthologies_dir(self) -> Path:
        """送别全集导出根目录(§3.6.3)。"""
        return self.resolved_data_dir() / "anthologies"

    # -- 派生:WebUI 端口(接线波 §4)---------------------------------------

    def resolved_ui_port(self) -> int:
        """``ui_port`` 未显式配置(0)时派生:streamable-http 复用 ``http_port``
        (同一 Starlette app,不新开端口);stdio 辅助面回落 8761。
        """
        if self.ui_port:
            return self.ui_port
        if self.transport == "streamable-http":
            return self.http_port
        return DEFAULT_UI_PORT_STDIO_FALLBACK

    def contract_overlay_path(self) -> Path:
        """WebUI 契约覆盖层路径(§4 路由契约;不存在时走出厂 contract_text())。"""
        return self.resolved_data_dir() / "contract.md"

    def persona_templates_dir(self) -> Path:
        """WebUI 人格模板目录(§4 路由契约 CRUD 面)。"""
        return self.resolved_data_dir() / "persona_templates"

    def ui_config_overlay_path(self) -> Path:
        """PUT api/config 写入的 server 级配置覆盖层(与 ``load()`` 读的同一个
        ``yelos.config.json``;§5.5 写锁 + 原子替换在 ui.config_store 实现)。

        优先用 ``config_source_path``(``load()`` 已经解析过一次的真实路径);
        非经 ``load()`` 直接构造 ``YelosConfig()`` 时(该字段空串)才现场按
        ``load()`` 同一套 env/默认文件名规则重新解析一次。
        """
        if self.config_source_path:
            return Path(self.config_source_path)
        cfg_path = os.environ.get("YELOS_CONFIG", "") or _CONFIG_FILENAME
        return Path(cfg_path)

    # -- 派生:有效有限性 / mode 校验 -------------------------------------

    def normalized_default_mode(self) -> str:
        """校验 default_mode;非法值回退 steward。"""
        return self.default_mode if self.default_mode in _VALID_MODES else DEFAULT_MODE

    def finitude_globally_on(self) -> bool:
        """幕 V 全局开关:finitude_enabled ∧ lifespan>0(§3.6.1)。

        per-session effective_finitude 还要叠加 mode==companion,由 session 层判。
        """
        return self.finitude_enabled and self.lifespan_active_days > 0

    # -- 派生:memory 配置(供 MemoryFacade 装配;缺键回落 MemoryConfig 默认)--

    def memory_config(self):
        """把 memory_enabled + memory_block 组装成 MemoryConfig(§C1 供血面)。

        惰性 import memory.contracts,避免 config 层强依赖 memory 包(config 仍
        零 core 依赖:memory 是纯逻辑,不引入 fastmcp/引擎)。memory_enabled 顶层
        键覆盖 block 里的同名键(顶层旗标优先)。
        """
        from .memory import MemoryConfig

        block = dict(self.memory_block) if isinstance(self.memory_block, dict) else {}
        block["memory_enabled"] = bool(self.memory_enabled)
        return MemoryConfig.from_dict(block)

    # -- 派生:安静时段解析(跨零点,§7.3 quiet_hours)--------------------

    def quiet_minutes(self) -> tuple[int, int]:
        """解析 "HH:MM-HH:MM" 为 (起, 止) 分钟;失败回退 01:00-08:00。"""
        try:
            start_raw, end_raw = self.quiet_hours.split("-")
            sh, sm = start_raw.split(":")
            eh, em = end_raw.split(":")
            qs = int(sh) * 60 + int(sm)
            qe = int(eh) * 60 + int(em)
            if not (0 <= qs < 1440 and 0 <= qe < 1440):
                return _QUIET_FALLBACK
            return qs, qe
        except (ValueError, AttributeError):
            return _QUIET_FALLBACK

    def in_quiet_hours(self, local_minutes: int) -> bool:
        """给定"当地一天内分钟数"判是否在安静时段;支持跨零点(23:00-07:00)。"""
        qs, qe = self.quiet_minutes()
        if qs == qe:
            return False
        if qs < qe:
            return qs <= local_minutes < qe
        # 跨零点:[qs,1440) ∪ [0,qe)
        return local_minutes >= qs or local_minutes < qe


# --- 装配 ---------------------------------------------------------------


def _first_nonempty(*values: str) -> str:
    """返回首个非空(strip 后)字符串;全空返回 ""。"""
    for v in values:
        if v and str(v).strip():
            return str(v)
    return ""


def _as_int(value: object, default: int) -> int:
    """防御式转 int;非法回退默认(config 不应因一个坏值崩)。"""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_bool(value: object, default: bool) -> bool:
    """防御式转 bool:识别 true/false/1/0/yes/no(字符串来自 env)。"""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _expand_env_ref(value: str) -> str:
    """展开 ${ENV} 引用(仅整串形如 ${NAME});非引用原样返回,缺失展开为空。"""
    text = str(value)
    if text.startswith("${") and text.endswith("}"):
        return os.environ.get(text[2:-1], "")
    return text


def _load_file(path: Path) -> dict:
    """读 yelos.config.json;不存在/损坏 → 空 dict(config 缺席不阻断启动)。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_assessor(block: object) -> AssessorModel | None:
    """从文件块解析 assessor_model;缺字段则视为未配置(None → 无 LLM degraded)。"""
    if not isinstance(block, dict):
        return None
    api_base = str(block.get("api_base", "")).strip()
    model = str(block.get("model", "")).strip()
    api_key = _expand_env_ref(block.get("api_key", ""))
    if not api_base or not model:
        return None
    return AssessorModel(api_base=api_base, api_key=api_key, model=model)


def _validate_evolution_overlay(cfg: "YelosConfig") -> None:
    """§3.8/X8 ghost-param 防线:REGISTRY 键须与 owner 模块参数面一致。

    只在"确有 evolution.overlay.json 被应用"时校验(D-E1:overlay 只在
    ``config.load()`` 这一单一入口读取)——``evolution_enabled`` 关或 overlay
    文件不存在均是 no-op,默认部署零感知、字节不漂移(不读 evolution 包、
    不建对象,同 ``build_evolution`` 的 T1/D-E3 纪律)。

    本函数只做校验,不把 genome 值写回 ``cfg``(``YelosConfig`` 是 frozen
    dataclass,且 session 热路径维持 evolution "NOT DRIVEN" 现状——wave A
    诊断裁定:那是另一个独立疑义,不在本次收尾范围内)。校验失败(REGISTRY
    引用了已改名/不存在的参数,或默认值越出声明域界)时清晰报错并指出具体
    的键,拒绝带着静默死账的 genome 继续装配。
    """
    if not cfg.evolution_enabled:
        return
    try:
        from .evolution.config_defaults import evolution_overlay_path
        from .evolution.genome.registry import validate_registry
        from .evolution.overlay import apply_overlay, load_overlay
    except ImportError:  # evolution extras 缺席,安静跳过(opt-in 纪律同款)
        return

    overlay_path = evolution_overlay_path(cfg.resolved_data_dir())
    overlay = load_overlay(overlay_path)
    if overlay is None:
        return  # 无 overlay(未生成/schema 坏):默认路径,不校验、不报错

    apply_overlay(overlay.get("values"))  # 兑现"overlay → genome 应用"这一步
    problems = validate_registry(cfg)
    if problems:
        detail = "; ".join(problems)
        raise ValueError(
            "YELOS evolution genome REGISTRY 校验失败(evolution.overlay.json "
            f"已生效,存在幽灵参数/域外默认值,拒绝带毒 genome 启动): {detail}"
        )


def load(config_path: str | os.PathLike | None = None) -> YelosConfig:
    """装配 YelosConfig:默认 ← 文件 ← env,优先级「文件 > env > 默认」。

    config_path 未给时,先看 $YELOS_CONFIG,再看 CWD 下 yelos.config.json。
    任何单键解析失败都回退默认,绝不 raise——配置坏一格不该拦住她醒来。
    """
    if config_path is None:
        config_path = os.environ.get("YELOS_CONFIG", "") or _CONFIG_FILENAME
    file_cfg = _load_file(Path(config_path))
    # sylanne.config.json 叠加层(§接线:人格侧配置装载)——优先级低于
    # yelos.config.json(后者显式覆盖前者),两者同缺则空 dict。与主配置同目录。
    syl_path = Path(config_path).parent / _SYLANNE_CONFIG_FILENAME
    syl_cfg = _load_file(syl_path)
    if syl_cfg:
        merged = dict(syl_cfg)
        merged.update(file_cfg)
        file_cfg = merged
    env = os.environ

    def pick_str(file_key: str, env_key: str, default: str) -> str:
        chosen = _first_nonempty(str(file_cfg.get(file_key, "")), env.get(env_key, ""))
        return chosen if chosen else default

    def pick_int(file_key: str, default: int) -> int:
        return _as_int(file_cfg.get(file_key, default), default)

    def pick_bool(file_key: str, default: bool, env_key: str = "") -> bool:
        """文件值优先;``env_key`` 给出时,文件缺该键才看 env(非空才生效)。"""
        if file_key in file_cfg:
            return _as_bool(file_cfg.get(file_key), default)
        if env_key:
            env_val = env.get(env_key, "")
            if env_val:
                return _as_bool(env_val, default)
        return default

    def pick_float(file_key: str, default: float) -> float:
        try:
            return float(file_cfg.get(file_key, default))
        except (TypeError, ValueError):
            return default

    transport = pick_str("transport", "YELOS_TRANSPORT", DEFAULT_TRANSPORT)
    if transport not in _VALID_TRANSPORTS:
        transport = DEFAULT_TRANSPORT

    # memory_block:接受文件里的 "memory" 段(dict);缺则空 dict → MemoryConfig 默认。
    memory_block = file_cfg.get("memory")
    if not isinstance(memory_block, dict):
        memory_block = {}

    cfg = YelosConfig(
        config_source_path=str(config_path),
        data_dir=pick_str("data_dir", "YELOS_DATA_DIR", DEFAULT_DATA_DIR),
        engine_data_dir=pick_str("engine_data_dir", "YELOS_ENGINE_DATA_DIR", ""),
        transport=transport,
        http_host=pick_str("http_host", "YELOS_HTTP_HOST", DEFAULT_HTTP_HOST),
        http_port=_as_int(
            env.get("YELOS_HTTP_PORT") or file_cfg.get("http_port"),
            DEFAULT_HTTP_PORT,
        ),
        default_mode=pick_str("default_mode", "YELOS_DEFAULT_MODE", DEFAULT_MODE),
        assessor_model=_parse_assessor(file_cfg.get("assessor_model")),
        arbiter_min_gap_seconds=pick_int(
            "arbiter_min_gap_seconds", DEFAULT_ARBITER_MIN_GAP_SECONDS
        ),
        express_trim_enabled=pick_bool("express_trim_enabled", True),
        heartbeat_enabled=pick_bool("heartbeat_enabled", True),
        intrinsic_interval_seconds=pick_int(
            "intrinsic_interval_seconds", DEFAULT_INTRINSIC_INTERVAL_SECONDS
        ),
        intrinsic_daily_cap=pick_int(
            "intrinsic_daily_cap", DEFAULT_INTRINSIC_DAILY_CAP
        ),
        quiet_hours=pick_str("quiet_hours", "YELOS_QUIET_HOURS", DEFAULT_QUIET_HOURS),
        dream_murmur_enabled=pick_bool("dream_murmur_enabled", True),
        shadow_enabled=pick_bool("shadow_enabled", True),
        finitude_enabled=pick_bool("finitude_enabled", True),
        lifespan_active_days=pick_int(
            "lifespan_active_days", DEFAULT_LIFESPAN_ACTIVE_DAYS
        ),
        heartbeat_max_sessions=pick_int(
            "heartbeat_max_sessions", DEFAULT_HEARTBEAT_MAX_SESSIONS
        ),
        farewell_token_ttl_seconds=pick_int(
            "farewell_token_ttl_seconds", DEFAULT_FAREWELL_TOKEN_TTL_SECONDS
        ),
        # -- WebUI 门面键(接线波 §4;默认 False = 与现状字节等价,§铁律 3)--
        ui_enabled=pick_bool("ui_enabled", DEFAULT_UI_ENABLED, "YELOS_UI"),
        ui_token=pick_str("ui_token", "YELOS_UI_TOKEN", DEFAULT_UI_TOKEN),
        ui_port=_as_int(
            env.get("YELOS_UI_PORT") or file_cfg.get("ui_port"), DEFAULT_UI_PORT
        ),
        ui_feed_full_text=pick_bool("ui_feed_full_text", DEFAULT_UI_FEED_FULL_TEXT),
        # -- 深化模块键(接线波 §2.4;默认 v0.1 兼容,routing 由 opt-in 旗标决定)--
        lang=pick_str("lang", "YELOS_LANG", DEFAULT_LANG),
        # guidance
        guidance_profile=pick_str(
            "guidance_profile", "YELOS_GUIDANCE_PROFILE", DEFAULT_GUIDANCE_PROFILE
        ),
        guidance_lang=pick_str("guidance_lang", "YELOS_GUIDANCE_LANG", DEFAULT_LANG),
        # primal
        primal_composer_enabled=pick_bool("primal_composer_enabled", False),
        primal_lexicon_profile=pick_str(
            "primal_lexicon_profile", "", DEFAULT_PRIMAL_LEXICON_PROFILE
        ),
        primal_template_enabled=pick_bool("primal_template_enabled", True),
        primal_markov_enabled=pick_bool("primal_markov_enabled", True),
        primal_markov_min_corpus=pick_int("primal_markov_min_corpus", 50),
        primal_closure_max=pick_int("primal_closure_max", DEFAULT_PRIMAL_CLOSURE_MAX),
        primal_routes=pick_str("primal_routes", "", ""),
        # intrinsic
        intrinsic_field_enabled=pick_bool("intrinsic_field_enabled", False),
        intrinsic_policy=pick_str(
            "intrinsic_policy", "", DEFAULT_INTRINSIC_POLICY
        ),
        intrinsic_integrator=pick_str(
            "intrinsic_integrator", "", DEFAULT_INTRINSIC_INTEGRATOR
        ),
        intrinsic_field_params=pick_str("intrinsic_field_params", "", "{}"),
        dream_generator=pick_str("dream_generator", "", DEFAULT_DREAM_GENERATOR),
        moments_enabled=pick_bool("moments_enabled", True),
        max_catchup_steps=pick_int("max_catchup_steps", DEFAULT_MAX_CATCHUP_STEPS),
        # arbiter
        arbiter_pipeline_enabled=pick_bool("arbiter_pipeline_enabled", False),
        arbiter_policy=pick_str("arbiter_policy", "", DEFAULT_ARBITER_POLICY),
        # shadow
        shadow_orchestrator_enabled=pick_bool("shadow_orchestrator_enabled", False),
        shadow_detector_set=pick_str(
            "shadow_detector_set", "", DEFAULT_SHADOW_DETECTOR_SET
        ),
        shadow_hypotheses=pick_int("shadow_hypotheses", DEFAULT_SHADOW_HYPOTHESES),
        shadow_intensity_fn=pick_str(
            "shadow_intensity_fn", "", DEFAULT_SHADOW_INTENSITY_FN
        ),
        shadow_engine_calls_per_beat=pick_int(
            "shadow_engine_calls_per_beat", DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT
        ),
        shadow_calibration_window=pick_int(
            "shadow_calibration_window", DEFAULT_SHADOW_CALIBRATION_WINDOW
        ),
        # finitude
        finitude_settle_enabled=pick_bool("finitude_settle_enabled", False),
        finitude_model=pick_str("finitude_model", "", DEFAULT_FINITUDE_MODEL),
        finitude_model_params=pick_str(
            "finitude_model_params", "", DEFAULT_FINITUDE_MODEL_PARAMS
        ),
        finitude_epoch_track=pick_str(
            "finitude_epoch_track", "", DEFAULT_FINITUDE_EPOCH_TRACK
        ),
        # memory(供血面,默认开)
        memory_enabled=pick_bool("memory_enabled", True),
        memory_block=memory_block,
        # distill / evolution(opt-in extras,默认关)
        distill_enabled=pick_bool("distill_enabled", DEFAULT_DISTILL_ENABLED),
        distill_model_dir=pick_str(
            "distill_model_dir", "", DEFAULT_DISTILL_MODEL_DIR
        ),
        distill_tier=pick_str("distill_tier", "", DEFAULT_DISTILL_TIER),
        distill_budget_ms=pick_int("distill_budget_ms", DEFAULT_DISTILL_BUDGET_MS),
        distill_k_candidates=pick_int(
            "distill_k_candidates", DEFAULT_DISTILL_K_CANDIDATES
        ),
        distill_reranker=pick_str("distill_reranker", "", DEFAULT_DISTILL_RERANKER),
        evolution_enabled=pick_bool("evolution_enabled", DEFAULT_EVOLUTION_ENABLED),
        evolution_velocity_bound=pick_float(
            "evolution_velocity_bound", DEFAULT_EVOLUTION_VELOCITY_BOUND
        ),
        evolution_min_days=pick_int("evolution_min_days", DEFAULT_EVOLUTION_MIN_DAYS),
        evolution_online_weight=pick_float(
            "evolution_online_weight", DEFAULT_EVOLUTION_ONLINE_WEIGHT
        ),
        evolution_strategy=pick_str(
            "evolution_strategy", "", DEFAULT_EVOLUTION_STRATEGY
        ),
    )
    _validate_evolution_overlay(cfg)
    return cfg
