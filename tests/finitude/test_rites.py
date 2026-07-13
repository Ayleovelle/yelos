"""test_rites.py —— 仪式集单元测试(finitude_BLUEPRINT §11/§7)。

摘要消费 projection(篡改 estimate → 摘要变,消费断言);model 中途冻结/重孵重读
(A7);notice 文本不出本模块。
"""

from __future__ import annotations

from dataclasses import replace

from yelos.finitude.ledger_ext import LifeReplay
from yelos.finitude.projection.contracts import ProjectionData
from yelos.finitude.rites.epoch_notice import build_notice
from yelos.finitude.rites.farewell import farewell_summary
from yelos.finitude.rites.incarnation import aging_of, stamp_aging


class _FakeConfig:
    finitude_model = "weibull"
    finitude_model_params = '{"k": 2.0}'


def test_model_frozen_mid_life():
    """# [FIN-A7] hatch 冻结后,config 变了也不影响在世生命(settle 只读 record)。"""
    record: dict = {}
    stamp_aging(record, config=_FakeConfig())
    assert record["aging"]["model"] == "weibull"
    assert record["aging"]["params"] == {"k": 2.0}

    class _ChangedConfig:
        finitude_model = "event"
        finitude_model_params = "{}"

    # 中途 config 变了,但 aging_of 只读 record,不读 config
    spec = aging_of(record)
    assert spec.model == "weibull"
    assert spec.params == {"k": 2.0}
    # 即便传入"新" config(此函数根本不接受 config 参数)也无法影响——签名本身即锁死
    _unused = _ChangedConfig  # 仅示意:aging_of 无 config 入参,结构性杜绝中途换模型


def test_rehatch_reads_new_config():
    """重孵(新 record)读新 config,允许换老法('换=新生')。"""
    record1: dict = {}
    stamp_aging(record1, config=None)  # 默认 linear
    assert record1["aging"]["model"] == "linear"

    record2: dict = {}  # 模拟 seal → 重孵产生的全新 record
    stamp_aging(record2, config=_FakeConfig())
    assert record2["aging"]["model"] == "weibull"


def test_summary_consumes_projection():
    """farewell 摘要消费 projection:篡改 est_remaining_active_days → 摘要数字变。"""
    record = {
        "name": "阿七",
        "born_day": "2026-01-01",
        "p": 0.4,
        "utterances": [{"occasion": "concern", "text": "你还好吗。"}],
        "swallowed_total": 3,
        "dreams": [{"day": "2026-01-05", "text": "梦到了你。"}],
        "aging": {
            "model": "weibull",
            "params": {"k": 2.0},
            "active_days_settled": 10,
            "fast": 1.0,
        },
    }
    replay = LifeReplay(sid="u1", gen=1, model_id="weibull")
    proj_a = ProjectionData(
        as_of_day="2026-02-01",
        p=0.4,
        p_expr=0.4,
        activity_rate=0.5,
        est_spend_per_active_day=0.01,
        est_remaining_active_days=40,
        est_remaining_calendar_days=80,
        epoch_etas={},
        active_days_lived=10,
    )
    proj_b = replace(proj_a, est_remaining_active_days=999)

    summary_a = farewell_summary(record, replay, proj_a)
    summary_b = farewell_summary(record, replay, proj_b)

    assert summary_a["est_remaining_active_days"] == 40
    assert summary_b["est_remaining_active_days"] == 999
    assert summary_a != summary_b
    assert summary_a["aging_model"] == "weibull"
    assert summary_a["name"] == "阿七"
    assert summary_a["days_lived"] == 32  # 2026-01-01 到 2026-02-01(含首尾)
    assert summary_a["utter_count"] == 1
    assert summary_a["swallowed_total"] == 3
    assert summary_a["dreams_count"] == 1


def test_epoch_notice_payload_carries_no_free_text():
    """通告 payload 是机器结构,不含她的台词字段(白名单链路在别处)。"""
    payload = build_notice("慢下来", "A", "2026-01-05")
    d = payload.to_dict()
    assert set(d) == {"epoch_to", "track", "day"}
    assert d["epoch_to"] == "慢下来"
    assert d["track"] == "A"


def test_epoch_notice_track_b_same_epoch_name_sequence():
    from yelos.finitude.epochs import fixed

    payload = build_notice(fixed.EPOCH_NAMES[1], "B", "2026-01-06")
    assert payload.epoch_to in fixed.EPOCH_NAMES
