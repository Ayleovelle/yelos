"""yelos —— 持久情感 MCP server(AstrBot 版 Yelos 的转世)。

The last word is her own.

包骨架层。协议面(server.py)/业务时序(session.py)/自发言语队列(outbox.py)/
八维行为提示(guidance.py)/引擎桥(engine_bridge.py)/持久化(persistence.py)/
配置(config.py)分文件落地(蓝图 §1.3)。core/ 为纯逻辑层,零 astrbot、零
sylanne_core、零 random(AST 测试锁死)。
"""

from __future__ import annotations

__version__ = "0.1.0"
