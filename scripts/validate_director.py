#!/usr/bin/env python3
"""AI 短剧导演稿的轻量结构与模板复读检查。"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path


FORBIDDEN = (
    "复合动作镜头组",
    "推进本场目标并留下可继承",
    "主体行动先于反应",
    "群体反应错开先后",
    "下一镜沿其视线或动作方向接入",
)

SHOT_RE = re.compile(r"^【镜头\s*(\d+)[^】]*】\s*$", re.MULTILINE)
SCENE_RE = re.compile(r"^##\s*场次[^\n]+$", re.MULTILINE)
FIELD_RE = re.compile(r"^(画面与表演|摄影与焦点|光线与材质|光声|声音|对白与口型|结束状态)[：:]\s*(.+)$")


def normalized_lines(block: str) -> list[str]:
    lines: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "【镜头", "对白与口型：")):
            continue
        match = FIELD_RE.match(line)
        body = match.group(2) if match else line
        body = re.sub(r"\s+", "", body)
        body = re.sub(r"[，。；：、！？,.!?:;\-—（）()\[\]【】]", "", body)
        if len(body) >= 24:
            lines.append(body)
    return lines


def validate(path: Path) -> tuple[list[str], int]:
    text = path.read_text(encoding="utf-8-sig")
    errors: list[str] = []

    for marker in ("【整集导演策略】", "空间连续：", "光声连续："):
        if marker not in text:
            errors.append(f"D7 缺少{marker}")

    scene_matches = list(SCENE_RE.finditer(text))
    if not scene_matches:
        errors.append("D7 缺少场次标题")

    matches = list(SHOT_RE.finditer(text))
    if not matches:
        errors.append("D9 缺少镜头标题")
        return errors, 0

    if scene_matches and any(match.start() < scene_matches[0].end() for match in matches):
        errors.append("D9 存在未归入任何场次的镜头")

    shot_numbers = [int(match.group(1)) for match in matches]
    duplicate_numbers = sorted(number for number, count in Counter(shot_numbers).items() if count > 1)
    if duplicate_numbers:
        errors.append(f"D9 镜头编号重复：{duplicate_numbers}")

    for index, scene_match in enumerate(scene_matches):
        end = scene_matches[index + 1].start() if index + 1 < len(scene_matches) else len(text)
        if not SHOT_RE.search(text[scene_match.end():end]):
            errors.append(f"D9 {scene_match.group(0).strip()}为空场次，至少需要一个镜头")

    all_lines: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        shot_name = match.group(0).strip()
        if not re.search(r"(?m)^画面与表演[：:]\s*\S", block):
            errors.append(f"D9 {shot_name}缺少画面与表演")
        if not re.search(r"(?m)^结束状态[：:]\s*\S", block):
            errors.append(f"D9 {shot_name}缺少结束状态")
        all_lines.extend(normalized_lines(block))

    for phrase in FORBIDDEN:
        count = text.count(phrase)
        if count:
            errors.append(f"D8 出现模板句“{phrase}”×{count}")

    duplicates = [(line, count) for line, count in Counter(all_lines).items() if count >= 3]
    for line, count in duplicates[:5]:
        errors.append(f"D8 完整描述重复{count}次：{line[:36]}")

    incompatible = ("晴白", "酸雨", "冻结冷蓝", "晨光暖白")
    for line_no, line in enumerate(text.splitlines(), 1):
        if sum(term in line for term in incompatible) >= 3:
            errors.append(f"D7 第{line_no}行并列多个互斥光线/天气方案")

    return errors, len(matches)


def self_test() -> int:
    valid = """# 第1集导演分解
【整集导演策略】
以人物犹疑和河水上涨建立压力。
空间连续：河岸入口在画面左侧，木桩为固定参照。
光声连续：阴天漫射光，河声从右后方持续。

## 场次1-1｜日/外｜河岸
【镜头01｜约6秒】
画面与表演: 禹从画面左侧走到木桩前停下，固定中景保留河面与他的视线关系；他触到湿绳后缩回手，呼吸顿住。
结束状态: 禹停在木桩左侧，右手悬在湿绳上方，视线落向上涨的河水。
"""
    invalid = """# 第1集导演分解
【整集导演策略】
测试。
空间连续：测试。
光声连续：测试。
## 场次1-1｜日/外｜河岸
【镜头01｜约6秒】
画面与表演：复合动作镜头组。
"""
    invalid_structure = """# 第1集导演分解
【整集导演策略】
测试。
空间连续：测试。
光声连续：测试。
## 场次1-1｜日/外｜河岸
【镜头01｜约6秒】
画面与表演：禹停在木桩前观察河水。
结束状态：禹的手停在湿绳上方。
## 场次1-2｜日/外｜堤岸
## 场次1-3｜日/外｜河湾
【镜头01｜约5秒】
画面与表演：禹沿着堤岸快步走向河湾。
结束状态：禹停在河湾入口处。
"""
    with tempfile.TemporaryDirectory() as tmp:
        ok_path = Path(tmp) / "ok.md"
        bad_path = Path(tmp) / "bad.md"
        bad_structure_path = Path(tmp) / "bad-structure.md"
        ok_path.write_text(valid, encoding="utf-8-sig")
        bad_path.write_text(invalid, encoding="utf-8-sig")
        bad_structure_path.write_text(invalid_structure, encoding="utf-8-sig")
        ok_errors, ok_shots = validate(ok_path)
        bad_errors, _ = validate(bad_path)
        bad_structure_errors, _ = validate(bad_structure_path)
    if ok_errors or ok_shots != 1:
        print("SELF-TEST FAIL: valid sample rejected")
        print("\n".join(ok_errors))
        return 1
    if not bad_errors or not any("D8" in error for error in bad_errors) or not any("结束状态" in error for error in bad_errors):
        print("SELF-TEST FAIL: invalid sample was not fully rejected")
        print("\n".join(bad_errors))
        return 1
    if not any("为空场次" in error for error in bad_structure_errors):
        print("SELF-TEST FAIL: empty scene accepted")
        print("\n".join(bad_structure_errors))
        return 1
    if not any("镜头编号重复" in error for error in bad_structure_errors):
        print("SELF-TEST FAIL: duplicate shot number accepted")
        print("\n".join(bad_structure_errors))
        return 1
    print("SELF-TEST PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.path is None:
        parser.error("请提供导演稿路径，或使用 --self-test")

    path = args.path
    if not path.exists():
        print(f"FAIL: 文件不存在：{path}")
        return 2

    paths = sorted(path.glob("*.md")) if path.is_dir() else [path]
    if not paths:
        print(f"FAIL: 目录中没有 Markdown 导演稿：{path}")
        return 2

    try:
        errors: list[str] = []
        shot_count = 0
        for item in paths:
            item_errors, item_shots = validate(item)
            if len(paths) > 1:
                errors.extend(f"{item.name}｜{error}" for error in item_errors)
            else:
                errors.extend(item_errors)
            shot_count += item_shots
    except UnicodeError as exc:
        print(f"FAIL: 文件编码错误：{exc}")
        return 2

    if errors:
        limit = 12
        for error in errors[:limit]:
            print(f"FAIL: {error}")
        if len(errors) > limit:
            print(f"FAIL: 另有{len(errors) - limit}项同类问题，先修复以上位置后再检查。")
        return 1

    scope = f"{len(paths)}份导演稿；" if len(paths) > 1 else ""
    print(f"PASS: {scope}{shot_count}个镜头；结构完整；未发现已知模板句或三镜复读。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
