"""受限 YAML 子集自著解析器(bench_BLUEPRINT §4.2,DSL 雏形)。

W1 交付面(蓝图称"雏形"/task 指令称"DSL 雏形"):最小可用文法子集——
缩进映射、列表(``- ``)、字符串/整数/布尔标量、``#`` 注释、空字典
``{}``/空列表 ``[]``。**无锚点、无多行标量、无流式集合**,超出文法即
解析错误并带行号。零第三方依赖(不引 pyyaml)。

文件顶层键固定 ``scenario_id / mode / config / days``,``days[].events[]``
直映 ``ScenarioEvent``。往返契约:``parse(dump(s)) == s``(测试
``test_dsl_roundtrip``)。

W1 只保证本文件描述的子集往返闭环;剧本库(``scenarios/library/``,入库
``.yel`` 文本)与语料表 ``corpus_zh.yel`` 留 W4(bench_BLUEPRINT §9)。
"""

from __future__ import annotations

from pathlib import Path

from .schema import Scenario, ScenarioDay, ScenarioEvent

__all__ = ["DslSyntaxError", "parse", "dump", "load_file", "dump_file"]


class DslSyntaxError(ValueError):
    """带行号的 DSL 解析错误(§4.2"错误报文带行号")。"""


_Token = tuple[int, str, int]  # (indent, text, lineno)


# ---------------------------------------------------------------------------
# 词法:剥注释/空行,量出缩进
# ---------------------------------------------------------------------------


def _strip_comment(line: str) -> str:
    """剥去行内 ``#`` 起的注释;不识别引号转义(W1 子集不需要)。

    简化纪律:若 ``#`` 出现在引号字符串内会被误剥——W1 子集的字符串标量
    (text_key 等)不含 ``#``,超出即视为使用者未遵守文法(不在此加复杂
    引号扫描机,保持 ~200 行体量,bench_BLUEPRINT §4.2 预算)。
    """
    idx = line.find("#")
    return line if idx == -1 else line[:idx]


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if line[:indent] != " " * indent or "\t" in raw[:indent] if indent else False:
            raise DslSyntaxError(f"第 {lineno} 行:缩进含 tab,仅允许空格")
        tokens.append((indent, line.strip(), lineno))
    return tokens


# ---------------------------------------------------------------------------
# 标量
# ---------------------------------------------------------------------------


def _parse_scalar(s: str, lineno: int):
    s = s.strip()
    if s == "":
        return None
    if s == "{}":
        return {}
    if s == "[]":
        return []
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s[0] in "'\"" or s[-1] in "'\"":
        raise DslSyntaxError(f"第 {lineno} 行:引号未闭合:{s!r}")
    return s


def _dump_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if v is None:
        return '""'
    s = str(v)
    if s != s.strip() or any(ch in s for ch in ":#\n") or s in ("true", "false"):
        return f'"{s}"'
    return s


def _split_kv(text: str, lineno: int) -> tuple[str, str | None]:
    if text.endswith(":"):
        return text[:-1].strip(), None
    idx = text.find(": ")
    if idx == -1:
        raise DslSyntaxError(f"第 {lineno} 行:映射行缺少 ': ' 分隔:{text!r}")
    return text[:idx].strip(), text[idx + 2 :].strip()


# ---------------------------------------------------------------------------
# 递归下降:映射 / 列表
# ---------------------------------------------------------------------------


def _parse_block(tokens: list[_Token], i: int, indent: int):
    """按 ``indent`` 层解析一个映射或列表块,返回 ``(value, next_i)``。"""
    if i >= len(tokens) or tokens[i][0] != indent:
        return {}, i
    if tokens[i][1].startswith("- "):
        return _parse_list(tokens, i, indent)
    return _parse_map(tokens, i, indent)


def _parse_map(tokens: list[_Token], i: int, indent: int):
    result: dict = {}
    while (
        i < len(tokens) and tokens[i][0] == indent and not tokens[i][1].startswith("- ")
    ):
        _, text, lineno = tokens[i]
        key, val = _split_kv(text, lineno)
        i += 1
        if val is None:
            if i < len(tokens) and tokens[i][0] > indent:
                child_indent = tokens[i][0]
                value, i = _parse_block(tokens, i, child_indent)
            else:
                value = {}
        else:
            value = _parse_scalar(val, lineno)
        result[key] = value
    return result, i


def _parse_list(tokens: list[_Token], i: int, indent: int):
    items: list = []
    while i < len(tokens) and tokens[i][0] == indent and tokens[i][1].startswith("- "):
        _, text, lineno = tokens[i]
        rest = text[2:]
        if rest in ("", "{}", "[]"):
            i += 1
            items.append(_parse_scalar(rest, lineno) if rest else {})
            continue
        if ": " in rest or rest.endswith(":"):
            key, val = _split_kv(rest, lineno)
            item_lines: list[_Token] = [(indent + 2, text[2:], lineno)]
            i += 1
            while i < len(tokens) and tokens[i][0] > indent:
                item_lines.append(tokens[i])
                i += 1
            value, _ = _parse_map(item_lines, 0, indent + 2)
            items.append(value)
        else:
            items.append(_parse_scalar(rest, lineno))
            i += 1
    return items, i


def _dump_block(obj, indent: int) -> list[str]:
    if isinstance(obj, dict):
        lines: list[str] = []
        for k, v in obj.items():
            if isinstance(v, dict):
                if not v:
                    lines.append(" " * indent + f"{k}: {{}}")
                else:
                    lines.append(" " * indent + f"{k}:")
                    lines.extend(_dump_block(v, indent + 2))
            elif isinstance(v, list):
                if not v:
                    lines.append(" " * indent + f"{k}: []")
                else:
                    lines.append(" " * indent + f"{k}:")
                    lines.extend(_dump_list(v, indent + 2))
            else:
                lines.append(" " * indent + f"{k}: {_dump_scalar(v)}")
        return lines
    raise DslSyntaxError(f"顶层块必须是映射,实得 {type(obj).__name__}")


def _dump_list(items: list, indent: int) -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            keys = list(item.items())
            if not keys:
                lines.append(" " * indent + "- {}")
                continue
            first_k, first_v = keys[0]
            if isinstance(first_v, (dict, list)):
                raise DslSyntaxError(f"列表项首键不得是嵌套结构(W1 子集限制):{first_k}")
            lines.append(" " * indent + f"- {first_k}: {_dump_scalar(first_v)}")
            rest = dict(keys[1:])
            lines.extend(_dump_block(rest, indent + 2))
        elif isinstance(item, list):
            raise DslSyntaxError("W1 子集不支持列表嵌套列表")
        else:
            lines.append(" " * indent + f"- {_dump_scalar(item)}")
    return lines


# ---------------------------------------------------------------------------
# Scenario <-> dict
# ---------------------------------------------------------------------------


def _event_from_dict(d: dict, lineno_hint: str = "") -> ScenarioEvent:
    try:
        return ScenarioEvent(
            at_min=int(d["at_min"]),
            kind=d["kind"],
            payload=dict(d.get("payload") or {}),
        )
    except KeyError as exc:
        raise DslSyntaxError(f"事件缺字段 {exc}{lineno_hint}") from exc


def _day_from_dict(d: dict) -> ScenarioDay:
    events = tuple(_event_from_dict(e) for e in d.get("events") or [])
    return ScenarioDay(day_index=int(d["day_index"]), events=events)


def _scenario_from_dict(d: dict) -> Scenario:
    try:
        days = tuple(_day_from_dict(x) for x in d.get("days") or [])
        return Scenario(
            scenario_id=d["scenario_id"],
            mode=d["mode"],
            days=days,
            config_overrides=dict(d.get("config") or {}),
            origin="dsl",
        )
    except KeyError as exc:
        raise DslSyntaxError(f"顶层缺字段 {exc}") from exc


def _scenario_to_dict(s: Scenario) -> dict:
    return {
        "scenario_id": s.scenario_id,
        "mode": s.mode,
        "config": dict(s.config_overrides),
        "days": [
            {
                "day_index": d.day_index,
                "events": [
                    {"at_min": e.at_min, "kind": e.kind, "payload": dict(e.payload)}
                    for e in d.events
                ],
            }
            for d in s.days
        ],
    }


# ---------------------------------------------------------------------------
# 公开面
# ---------------------------------------------------------------------------


def parse(text: str) -> Scenario:
    """解析 ``.yel`` 文本为 ``Scenario``。语法错误抛 ``DslSyntaxError`` 带行号。"""
    tokens = _tokenize(text)
    if not tokens:
        raise DslSyntaxError("第 1 行:空文档")
    top, i = _parse_map(tokens, 0, tokens[0][0])
    if i != len(tokens):
        _, _, lineno = tokens[i]
        raise DslSyntaxError(f"第 {lineno} 行:顶层缩进不一致,解析未消费全部内容")
    return _scenario_from_dict(top)


def dump(scenario: Scenario) -> str:
    """序列化 ``Scenario`` 为 ``.yel`` 文本,与 ``parse`` 互逆。"""
    lines = _dump_block(_scenario_to_dict(scenario), 0)
    return "\n".join(lines) + "\n"


def load_file(path: Path) -> Scenario:
    return parse(Path(path).read_text(encoding="utf-8"))


def dump_file(scenario: Scenario, path: Path) -> None:
    Path(path).write_text(dump(scenario), encoding="utf-8")
