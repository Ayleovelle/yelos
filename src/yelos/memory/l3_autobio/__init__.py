"""l3_autobio 子包在架构中的位置。

红队 major⑧ 承诺 2 的正身:主题节点带 born/grow/merge/split/dormant/wake/
dead 事件流的生命周期状态机(MEM-A6)。lifecycle.py 是状态机+持久化,
cluster.py 是夜窗聚类判定(双证据、确定性)。二者只经 contracts 类型与
l2_semantic.linalg_lite.cosine 耦合。
"""

from __future__ import annotations

from .lifecycle import TopicStore, replay_members
from .cluster import compute_centroid

__all__ = ["TopicStore", "replay_members", "compute_centroid"]
