#!/usr/bin/env python3
"""Fast structural check for normal Chinese short-drama screenplay files."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


EPISODE_RE = re.compile(r"^第\s*(\d+)\s*集(?:\s+.+)?$", re.M)
SCENE_RE = re.compile(
    r"^(\d+)-(\d+)\s+(日|夜|晨|昏|连续)\s*/\s*(内|外|内外)\s+(.+?)\s*$",
    re.M,
)
FORBIDDEN = (
    "【剧情节拍",
    "场面正文：",
    "场面结果：",
    "镜头号：",
    "焦段：",
    "运镜：",
)


def validate_text(text: str) -> list[str]:
    errors: list[str] = []
    episodes = list(EPISODE_RE.finditer(text))
    episode = episodes[0] if episodes else None
    if not episodes:
        errors.append("缺少“第N集”标题")
    elif len(episodes) != 1:
        errors.append(f"“第N集”标题应出现1次，实际{len(episodes)}次")
    if not re.search(r"^建议时长：\s*约?\s*\d+\s*秒\s*$", text, re.M):
        errors.append("缺少“建议时长：约N秒”")

    scenes = list(SCENE_RE.finditer(text))
    if not scenes:
        errors.append("缺少正常场次标题，例如“1-1 日/内  场景名”")
    else:
        episode_no = int(episode.group(1)) if episode else None
        expected_scene = 1
        for index, match in enumerate(scenes):
            scene_episode = int(match.group(1))
            scene_no = int(match.group(2))
            if episode_no is not None and scene_episode != episode_no:
                errors.append(f"场次 {match.group(0)!r} 的集号与标题不一致")
            if scene_no != expected_scene:
                errors.append(f"场次编号应为 {expected_scene}，实际为 {scene_no}")
                expected_scene = scene_no
            expected_scene += 1

            start = match.end()
            end = scenes[index + 1].start() if index + 1 < len(scenes) else len(text)
            block = text[start:end]
            if not re.search(r"^人物：\s*\S.*$", block, re.M):
                errors.append(f"场次 {scene_episode}-{scene_no} 缺少人物行")
            if not re.search(r"^△\s*\S.+$", block, re.M):
                errors.append(f"场次 {scene_episode}-{scene_no} 缺少可见动作")

    for token in FORBIDDEN:
        if token in text:
            errors.append(f"包含分镜式字段：{token}")
    if re.search(r"^【?节拍\s*V?\d+", text, re.M | re.I):
        errors.append("包含节拍编号")
    if re.search(r"^B\d+(?:\.\d+)?\b", text, re.M | re.I):
        errors.append("包含 Bn 节拍格式")
    ending_count = text.count("【本集完】")
    if ending_count != 1:
        errors.append(f"“【本集完】”应出现1次，实际{ending_count}次")
    return errors


def validate_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return ["文件不是 UTF-8 编码"]
    except OSError as exc:
        return [f"文件读取失败：{exc}"]
    return validate_text(text)


def self_test() -> int:
    valid = """《测试剧》
第1集  倒计时
建议时长：约90秒

1-1 日/内  公寓
人物：禹

△ 水杯里的水逆流回水龙头。
禹：先离开这里。

1-2 夜/外  站台
人物：林瑞、苏钰

△ 无人列车在两人面前打开车门。
苏钰：它在等我们。

1-3 晨/外  河岸
人物：无

△ 河水漫过刻在泥地上的最后一道线。

【本集完】
"""
    invalid = """第1集
建议时长：约90秒
【剧情节拍B1】
场面正文：林瑞逃跑。
场面结果：成功。
【本集完】
"""
    duplicate_structure = valid.replace(
        "建议时长：约90秒\n",
        "第1集  重复标题\n建议时长：约90秒\n",
    ).replace("【本集完】", "【本集完】\n【本集完】")
    with tempfile.TemporaryDirectory() as tmp:
        ok_path = Path(tmp) / "ok.md"
        bad_path = Path(tmp) / "bad.md"
        ok_path.write_text(valid, encoding="utf-8-sig")
        bad_path.write_text(invalid, encoding="utf-8-sig")
        duplicate_path = Path(tmp) / "duplicate.md"
        duplicate_path.write_text(duplicate_structure, encoding="utf-8-sig")
        missing_path = Path(tmp) / "not-found.md"
        ok_errors = validate_file(ok_path)
        bad_errors = validate_file(bad_path)
        duplicate_errors = validate_file(duplicate_path)
        missing_errors = validate_file(missing_path)
    if ok_errors:
        print("SELF-TEST FAIL: valid sample rejected")
        print("\n".join(ok_errors))
        return 1
    if not bad_errors:
        print("SELF-TEST FAIL: invalid sample accepted")
        return 1
    if not any("标题应出现1次" in error for error in duplicate_errors):
        print("SELF-TEST FAIL: duplicate episode title accepted")
        print("\n".join(duplicate_errors))
        return 1
    if not any("本集完" in error and "实际2次" in error for error in duplicate_errors):
        print("SELF-TEST FAIL: duplicate ending accepted")
        print("\n".join(duplicate_errors))
        return 1
    if not any("文件读取失败" in error for error in missing_errors):
        print("SELF-TEST FAIL: missing file was not handled")
        print("\n".join(missing_errors))
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
        parser.error("请提供剧本文件路径，或使用 --self-test")
    if not args.path.is_file():
        print(f"FAIL: 文件不存在：{args.path}")
        return 2
    errors = validate_file(args.path)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
