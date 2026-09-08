#!/usr/bin/env python3
"""Fast structural checks for self-contained asset prompts and selected layout contracts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SLOT_RE = re.compile(r"(?m)^【资产位】(?P<value>[^\r\n]*)$")
NAME_RE = re.compile(r"(?m)^【资产名称】(?P<value>[^\r\n]*)$")
LAYOUT_RE = re.compile(r"(?m)^【布局合同】(?P<value>[^\r\n]+)$")
PROMPT_MARK = "给生图模型的提示词："
MODULES = ("【风格】", "【正向提示词】", "【负面提示词】")
DEFAULT_LAYOUT = "默认Skill资产板"
USER_LAYOUT_PREFIX = "用户确认模板："
MAX_ERRORS = 40

NONHUMAN_MARKERS = (
    "非人", "机器人", "机械体", "无人机", "智能体", "仿生体",
    "兽形", "动物角色", "生物角色", "神兽", "怪物",
)
SLOT_RULES = {
    "人物": re.compile(r"^@人物P\d{2,}[-—]\S.*$"),
    "场景": re.compile(r"^@场景S\d{2,}[-—]\S.*$"),
    "道具": re.compile(r"^@道具D\d{2,}[-—]\S.*$"),
    "特效": re.compile(r"^@特效F\d{2,}[-—]\S.*$"),
}


def is_nonhuman_prompt(prompt: str) -> bool:
    return any(token in prompt for token in NONHUMAN_MARKERS)


def parse_slot(value: str, legacy: bool = False) -> tuple[str | None, str | None]:
    value = value.strip()
    for kind, pattern in SLOT_RULES.items():
        if pattern.fullmatch(value):
            return kind, None
    if legacy and re.fullmatch(r"^@特效FX\d{2,}[-—]\S.*$", value):
        return "特效", None
    return None, f"资产槽位格式错误或类别前缀不匹配：{value or '空值'}"


def parse_layout_contract(text: str, legacy: bool = False) -> tuple[str | None, str | None, list[str]]:
    matches = LAYOUT_RE.findall(text)
    if legacy and not matches:
        return "legacy", None, []
    if len(matches) != 1:
        return None, None, [f"布局合同标记应出现1次，实际{len(matches)}次"]
    value = matches[0].strip()
    if value == DEFAULT_LAYOUT:
        return "default", None, []
    if value.startswith(USER_LAYOUT_PREFIX):
        name = value[len(USER_LAYOUT_PREFIX):].strip()
        if not name:
            return None, None, ["用户确认模板缺少模板名称"]
        return "user", name, []
    return None, None, [f"未知布局合同：{value}"]


def split_modules(slot: str, content: str) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    positions: list[int] = []
    for module in MODULES:
        count = content.count(module)
        if count != 1:
            errors.append(f"{slot}: {module}应出现1次，实际{count}次")
        positions.append(content.find(module))
    if errors:
        return {}, errors
    if positions != sorted(positions):
        return {}, [f"{slot}: 模块顺序必须为风格→正向提示词→负面提示词"]

    values: dict[str, str] = {}
    for index, module in enumerate(MODULES):
        start = positions[index] + len(module)
        end = positions[index + 1] if index + 1 < len(MODULES) else len(content)
        value = content[start:end].strip()
        values[module] = value
        if not value:
            errors.append(f"{slot}: {module}内容为空")
    return values, errors


def validate_human_default(slot: str, positive: str) -> list[str]:
    errors: list[str] = []
    head = positive[:620]
    if "4张完整全身" not in head or "1张脸部" not in head:
        errors.append("正向提示词开头未先声明4张完整全身图+1张脸部特写")
    if not all(token in head for token in ("左侧40%", "右侧60%", "上55%", "下45%")):
        errors.append("正向提示词开头未闭合左40/右60和右侧55/45分区")
    if not all(token in positive for token in ("右上区", "严格正面", "纯侧面", "严格背面", "右下")):
        errors.append("正侧背与右下脸部视图任务不完整")
    if "五视图" in positive[:180]:
        errors.append("正向提示词开头仍使用含混的五视图简称")
    if not any(token in positive for token in ("不是五张等大横排", "禁止五张等大", "五张等大全身")):
        errors.append("缺少防止五张等大全身横排的排除语句")
    if not all(token in positive for token in ("标尺", "百分比", "参数标签")):
        errors.append("缺少标尺/百分比/参数标签排除语句")
    return [f"{slot}: {message}" for message in errors]


def validate_default_layout(slot: str, kind: str, positive: str) -> list[str]:
    errors: list[str] = []
    if kind in ("人物", "道具") and "纯白" not in positive[:260]:
        errors.append(f"{slot}: 默认合同下人物/道具开头缺少纯白背景")
    if kind == "人物":
        if is_nonhuman_prompt(positive):
            if not all(token in positive for token in ("左侧", "右侧", "正面", "侧面", "背面", "特写")):
                errors.append(f"{slot}: 非人角色主图区、正侧背和结构特写任务不完整")
        else:
            errors.extend(validate_human_default(slot, positive))
    elif kind in ("道具", "场景"):
        if not all(token in positive for token in ("左侧", "右侧", "分隔线")):
            errors.append(f"{slot}: 默认主图区/验证区分隔合同不完整")
        if not any(token in positive for token in ("验证格", "验证区", "等高纵向格", "辅助格")):
            errors.append(f"{slot}: 默认右侧验证格任务不明确")
    return errors


def iter_asset_blocks(text: str):
    matches = list(SLOT_RE.finditer(text))
    for index, match in enumerate(matches):
        value = match.group("value").strip()
        previous_end = matches[index - 1].end() if index else 0
        names = [name.strip() for name in NAME_RE.findall(text[previous_end:match.start()])]
        raw_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():raw_end]
        next_name = NAME_RE.search(block)
        if next_name:
            block = block[:next_name.start()]
        prompt_count = block.count(PROMPT_MARK)
        marker = block.find(PROMPT_MARK)
        content = "" if marker < 0 else block[marker + len(PROMPT_MARK):].strip()
        yield match.group(0).strip(), value, names, prompt_count, content


def validate_text(text: str, legacy: bool = False) -> tuple[list[str], int, str]:
    mode, template_name, errors = parse_layout_contract(text, legacy=legacy)
    checked = 0
    seen_slots: set[str] = set()
    seen_names: set[str] = set()
    slot_count = len(SLOT_RE.findall(text))
    name_count = len(NAME_RE.findall(text))
    if not legacy and name_count != slot_count:
        errors.append(f"资产名称与资产位数量不一致：名称{name_count}个，资产位{slot_count}个")
    for slot_line, slot_value, names, prompt_count, content in iter_asset_blocks(text):
        checked += 1
        kind, slot_error = parse_slot(slot_value, legacy=legacy)
        slot_label = slot_value or slot_line
        if slot_error:
            errors.append(f"{slot_line}: {slot_error}")
        elif slot_value in seen_slots:
            errors.append(f"{slot_value}: 资产槽位重复")
        else:
            seen_slots.add(slot_value)
        if not legacy:
            if len(names) != 1:
                errors.append(f"{slot_label}: 前方应有且只能有一个【资产名称】，实际{len(names)}个")
            elif not names[0]:
                errors.append(f"{slot_label}: 【资产名称】内容为空")
            elif names[0] in seen_names:
                errors.append(f"{slot_label}: 资产名称重复：{names[0]}")
            else:
                seen_names.add(names[0])
        if prompt_count != 1:
            errors.append(f"{slot_label}: {PROMPT_MARK}应出现1次，实际{prompt_count}次")
        if not content or prompt_count != 1:
            if not content:
                errors.append(f"{slot_label}: 缺少生图提示词")
            continue
        modules, module_errors = split_modules(slot_label, content)
        errors.extend(module_errors)
        if not modules:
            continue
        positive = modules["【正向提示词】"]
        negative = modules["【负面提示词】"]
        if "水印" not in negative or not any(token in negative for token in ("文字", "标签")):
            errors.append(f"{slot_label}: 负面提示词未同时覆盖文字/标签与水印")
        if mode == "default" and kind is not None:
            errors.extend(validate_default_layout(slot_label, kind, positive))
    if checked == 0:
        errors.append("未找到可检查的资产提示词")
    if mode == "default":
        label = DEFAULT_LAYOUT
    elif mode == "user":
        label = f"用户确认模板：{template_name}"
    elif mode == "legacy":
        label = "旧合同（未迁移）"
    else:
        label = "无效合同"
    return errors, checked, label


def self_test() -> int:
    default_valid = """# 全剧资产
【布局合同】默认Skill资产板
【资产名称】禹
【资产位】@人物P01-禹
给生图模型的提示词：
【风格】历史写实，夯土与粗织物的自然质感。
【正向提示词】16:9横版，纯白背景，4张完整全身图＋1张脸部特写；左侧40%整高主图，右侧60%验证区，右侧上55%为右上区，放严格正面、纯侧面、严格背面，右侧下45%为右下脸部特写。不是五张等大横排；画面不显示标尺、百分比、参数标签。
【负面提示词】禁止文字、标签、水印、异脸异服。
"""
    user_valid = """# 全剧资产
【布局合同】用户确认模板：青铜器环形验证板
【资产名称】礼器
【资产位】@道具D01-礼器
给生图模型的提示词：
【风格】考古写实与自然氧化铜质感。
【正向提示词】使用已确认的环形校验板：16:9米灰底，左侧三分之二放完整主图，右侧一列四格，依次放正面、侧面、俯看和接口特写，各格分别核对器形、厚度、口沿和底部结构。
【负面提示词】禁止文字、标签、水印、错误器形。
"""
    no_contract = user_valid.replace("【布局合同】用户确认模板：青铜器环形验证板\n", "")
    empty_positive = default_valid.replace(
        "【正向提示词】16:9横版，纯白背景，4张完整全身图＋1张脸部特写；左侧40%整高主图，右侧60%验证区，右侧上55%为右上区，放严格正面、纯侧面、严格背面，右侧下45%为右下脸部特写。不是五张等大横排；画面不显示标尺、百分比、参数标签。",
        "【正向提示词】",
    )
    missing_name = default_valid.replace("【资产名称】禹\n", "")
    invalid_slot = default_valid.replace("@人物P01-禹", "@人物S01-禹")
    duplicate_slot = default_valid + default_valid.replace(
        "【布局合同】默认Skill资产板\n", ""
    ).replace("【资产名称】禹", "【资产名称】另一位禹")
    duplicate_name = default_valid + default_valid.replace(
        "【布局合同】默认Skill资产板\n", ""
    ).replace("@人物P01-禹", "@人物P02-禹")
    legacy_fx = user_valid.replace("【布局合同】用户确认模板：青铜器环形验证板\n", "").replace(
        "@道具D01-礼器", "@特效FX01-显影"
    )
    default_errors, default_count, _ = validate_text(default_valid)
    user_errors, user_count, _ = validate_text(user_valid)
    missing_contract_errors, _, _ = validate_text(no_contract)
    legacy_errors, legacy_count, legacy_label = validate_text(no_contract, legacy=True)
    empty_errors, _, _ = validate_text(empty_positive)
    missing_name_errors, _, _ = validate_text(missing_name)
    invalid_slot_errors, _, _ = validate_text(invalid_slot)
    duplicate_slot_errors, _, _ = validate_text(duplicate_slot)
    duplicate_name_errors, _, _ = validate_text(duplicate_name)
    legacy_fx_errors, legacy_fx_count, _ = validate_text(legacy_fx, legacy=True)
    if default_errors or default_count != 1:
        print("SELF-TEST FAIL: default contract rejected")
        print("\n".join(default_errors))
        return 1
    if user_errors or user_count != 1:
        print("SELF-TEST FAIL: user contract rejected")
        print("\n".join(user_errors))
        return 1
    if not missing_contract_errors:
        print("SELF-TEST FAIL: missing contract accepted")
        return 1
    if legacy_errors or legacy_count != 1 or "旧合同" not in legacy_label:
        print("SELF-TEST FAIL: valid legacy sample rejected")
        print("\n".join(legacy_errors))
        return 1
    if not any("内容为空" in error for error in empty_errors):
        print("SELF-TEST FAIL: empty module accepted")
        print("\n".join(empty_errors))
        return 1
    if not any("资产名称" in error for error in missing_name_errors):
        print("SELF-TEST FAIL: missing asset name accepted")
        print("\n".join(missing_name_errors))
        return 1
    if not any("槽位格式错误" in error for error in invalid_slot_errors):
        print("SELF-TEST FAIL: invalid asset slot accepted")
        print("\n".join(invalid_slot_errors))
        return 1
    if not any("资产槽位重复" in error for error in duplicate_slot_errors):
        print("SELF-TEST FAIL: duplicate asset slot accepted")
        print("\n".join(duplicate_slot_errors))
        return 1
    if not any("资产名称重复" in error for error in duplicate_name_errors):
        print("SELF-TEST FAIL: duplicate asset name accepted")
        print("\n".join(duplicate_name_errors))
        return 1
    if legacy_fx_errors or legacy_fx_count != 1:
        print("SELF-TEST FAIL: legacy FX slot rejected in legacy mode")
        print("\n".join(legacy_fx_errors))
        return 1
    print("SELF-TEST PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_markdown", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="按布局合同标记出现以前的旧格式检查")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.asset_markdown is None:
        parser.error("请提供资产Markdown路径，或使用 --self-test")
    try:
        text = args.asset_markdown.read_text(encoding="utf-8-sig")
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors, checked, label = validate_text(text, legacy=args.legacy)
    if errors:
        print("FAIL")
        for error in errors[:MAX_ERRORS]:
            print(f"- {error}")
        if len(errors) > MAX_ERRORS:
            print(f"- 其余{len(errors) - MAX_ERRORS}项已省略")
        return 1
    print(f"PASS: {checked}个资产具备独立三模块；布局合同={label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
