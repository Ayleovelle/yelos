"""在整个架构中的位置:primal 包内唯一 hashlib 落点(蓝图 §10)。

全部选词/选变体/选纪元固化种子的确定性都经本文件的三个函数落地;
除本文件外,primal/**下任何 .py 都不得 import hashlib
(test_determinism_registry.py 的 AST 锁断言此事)。

KEY_REGISTRY 是键型的文档化契约:新增键型必须先在此登记(键 id、格式、
粒度、消费者、稳定性承诺),再在代码里使用——注册表是唯一事实源,
不是事后补写的文档。
"""

from __future__ import annotations

import hashlib

# --- §10 键型注册表(文档化契约,只增不删)--------------------------------

KEY_REGISTRY: dict[str, dict[str, str]] = {
    "pick": {
        "format": "{sid}|{day_key}|{occasion}",
        "granularity": "day",
        "consumer": "lexicon 选词(v0.1 原键,逐字不变)",
        "stability": "frozen",
    },
    "tpl_pat": {
        "format": "{sid}|{day_key}|{occasion}|tpl|pat",
        "granularity": "day",
        "consumer": "template 选 pattern",
        "stability": "new",
    },
    "tpl_slot": {
        "format": "{sid}|{day_key}|{occasion}|tpl|{slot_id}",
        "granularity": "day",
        "consumer": "template 槽位填充",
        "stability": "new",
    },
    "mkv_step": {
        "format": "{sid}|{day_key}|{occasion}|mkv|{i}",
        "granularity": "day·步",
        "consumer": "markov 步进",
        "stability": "new",
    },
    "prosody": {
        "format": "{sid}|{day_key}|pros|{occasion}|{blake2b(canonical)[:8]}",
        "granularity": "消息",
        "consumer": "韵律变体选择",
        "stability": "new",
    },
    "morph_seed": {
        "format": "{sid}|{incarnation}|morph_seed",
        "granularity": "一生",
        "consumer": "纪元固化口头禅",
        "stability": "new",
    },
    "rerank": {
        "format": "{sid}|{day_key}|{occasion}|rr|{blake2b(cand)[:8]}",
        "granularity": "消息",
        "consumer": "distilled 候选重排(M9 预留,未启用)",
        "stability": "reserved",
    },
    # --- W2 intrinsic 新键型登记(INTEGRATION_SPEC §2.4 / intrinsic_BLUEPRINT §6.4)---
    "poisson": {
        "format": "poisson|{sid}|{day_key}|{tick_index}",
        "granularity": "心跳拍",
        "consumer": "intrinsic.impulses.poisson_budget.PoissonBudgetPolicy(哈希 thinning)",
        "stability": "new",
    },
    "dream": {
        "format": "dream|{sid}|{day_key}|{theme_keys_joined}",
        "granularity": "日",
        "consumer": "intrinsic.dreamwork.wander.MarkovWander 漫游 / primal dream_murmur 选句",
        "stability": "new",
    },
    "batch": {
        "format": "batch|{sid}",
        "granularity": "session",
        "consumer": "intrinsic.scheduler.heartbeat 心跳错峰批次划分",
        "stability": "new",
    },
    # --- W5 distill 新键型登记(INTEGRATION_SPEC §3.8 / distill_BLUEPRINT §3.1)---
    # 与上方预留的 "rerank" 键(格式含 blake2b(cand),M9 占位)不是同一键;
    # 二者不冲突(INTEGRATION_SPEC 明文核对),"rerank" 保持 reserved 不使用。
    "distill": {
        "format": "{sid}|{day_key}|distill|{occasion}",
        "granularity": "日·场合",
        "consumer": "distill.runtime.rerank(HashRerank/FidelityRerank 候选选择)",
        "stability": "new",
    },
    # --- W5 evolution 新键型登记(INTEGRATION_SPEC §3.9 / evolution_BLUEPRINT §2.2)---
    "evo": {
        "format": "evo|{deployment_id}|{gen}|{strategy}|{key} "
        "(平手键: evo|{deployment_id}|{gen}|tie)",
        "granularity": "世代",
        "consumer": "evolution.variation.base.evo_hash_unit / evo_tie_hash_unit"
        "(变异提案确定性哈希)",
        "stability": "new",
    },
}


def h_byte(key: str) -> int:
    """sha256(key).digest()[0](v0.1 语义,逐字不变;供 pick 兼容闸复用)。"""
    return hashlib.sha256(key.encode("utf-8")).digest()[0]


def h_bytes(key: str, n: int) -> bytes:
    """取 n 字节的确定性字节流(markov 多步选择用);key 内含步序,故不必

    在这里滚动计数器——调用方应把步序编码进 key 本身(见 mkv_step)。
    当 n 超过单次 sha256 摘要长度(32 字节)时用计数器扩展,保持确定性。
    """
    if n <= 0:
        return b""
    out = bytearray()
    counter = 0
    while len(out) < n:
        digest = hashlib.sha256(f"{key}#{counter}".encode("utf-8")).digest()
        out.extend(digest)
        counter += 1
    return bytes(out[:n])


def text_digest(text: str) -> str:
    """blake2b 短摘(消息粒度键用,如 prosody/rerank 键里的 [:8] 段)。"""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=4).hexdigest()
