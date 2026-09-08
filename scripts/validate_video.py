#!/usr/bin/env python3
"""视频提示词的轻量自包含结构、模块顺序与资产槽位检查。"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


SEGMENT_RE = re.compile(r"^【片段\s*V(\d+)[^】]*】\s*$", re.MULTILINE)
REF_LINE_RE = re.compile(r"^@图片(\d+)\s*=\s*(\S.*)$")
ASSET_SLOT_RE = re.compile(r"^@(?:人物P|场景S|道具D|特效F)\d{2,}[-—]\S.*$")
LOOKUP_MARKER = "【工作人员找图清单】"
LOOKUP_LINE_RE = re.compile(r"^片段V(\d+)\s*｜\s*@图片(\d+)\s*=\s*(\S.*)$")
REQUIRED = ("【参考图片】", "【风格】", "【视频提示词】", "【对白与声音】", "【负面提示词】", "【结束状态】")


def module_body(block: str, start_marker: str, end_marker: str | None) -> str:
    start = block.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = block.find(end_marker, start) if end_marker else len(block)
    if end < 0:
        end = len(block)
    return block[start:end].strip()


def validate_text(text: str, legacy: bool = False) -> tuple[list[str], int]:
    errors: list[str] = []
    expected_lookup: list[tuple[int, int, str]] = []
    matches = list(SEGMENT_RE.finditer(text))
    if not matches:
        return ["V9 缺少片段标题"], 0

    prefix = text[:matches[0].start()]
    for marker in ("【风格】", "【声音总则】", "【对白与声音】", "【负面提示词】"):
        if marker in prefix:
            errors.append(f"V9 第一条片段之前存在孤立模块{marker}")
    if "【声音总则】" in text:
        errors.append("V8 不得使用整集【声音总则】，声音必须写进每个片段")

    actual_segments = [int(match.group(1)) for match in matches]
    expected_segments = list(range(1, len(matches) + 1))
    if actual_segments != expected_segments:
        errors.append(f"V9 片段编号不连续：{actual_segments}")

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        segment = f"V{match.group(1)}"
        positions: list[int] = []
        for marker in REQUIRED:
            count = block.count(marker)
            if count != 1:
                errors.append(f"V9 {segment}的{marker}应出现一次，当前{count}次")
            positions.append(block.find(marker))
        if all(position >= 0 for position in positions) and positions != sorted(positions):
            errors.append(f"V9 {segment}模块顺序错误")

        body_specs = (
            ("【风格】", "【视频提示词】", "V7", "风格"),
            ("【视频提示词】", "【对白与声音】", "V4", "视频提示词"),
            ("【对白与声音】", "【负面提示词】", "V8", "对白与声音"),
            ("【负面提示词】", "【结束状态】", "V11", "负面提示词"),
            ("【结束状态】", "【工作人员找图清单】", "V6", "结束状态"),
        )
        for start_marker, end_marker, code, label in body_specs:
            if block.count(start_marker) == 1 and not module_body(block, start_marker, end_marker):
                errors.append(f"{code} {segment}的{label}模块内容为空")

        ref_section = module_body(block, "【参考图片】", "【风格】")
        ref_matches: list[tuple[str, str]] = []
        for line in (line.strip() for line in ref_section.splitlines() if line.strip()):
            ref_match = REF_LINE_RE.fullmatch(line)
            if not ref_match:
                errors.append(f"V2 {segment}存在无法识别的参考图片映射行：{line}")
                continue
            ref_matches.append((ref_match.group(1), ref_match.group(2)))
        refs = [int(number) for number, _ in ref_matches]
        if not refs:
            errors.append(f"V2 {segment}没有参考图片映射")
        elif refs != list(range(1, len(refs) + 1)):
            errors.append(f"V2 {segment}参考图片编号不从1连续：{refs}")
        for number, value in ref_matches:
            value = value.strip()
            if not legacy and not ASSET_SLOT_RE.fullmatch(value):
                errors.append(f"V2 {segment}的@图片{number}未绑定稳定资产槽位：{value.strip()}")
            expected_lookup.append((int(match.group(1)), int(number), value))

        negative = module_body(block, "【负面提示词】", "【结束状态】")
        if "字幕" not in negative:
            errors.append(f"V11 {segment}负面提示词未禁止字幕")
        if "水印" not in negative:
            errors.append(f"V11 {segment}负面提示词未禁止水印")

    if not legacy:
        lookup_count = text.count(LOOKUP_MARKER)
        if lookup_count != 1:
            errors.append(f"V2 {LOOKUP_MARKER}应出现一次，当前{lookup_count}次")
        else:
            lookup_position = text.find(LOOKUP_MARKER)
            if lookup_position < matches[-1].end():
                errors.append(f"V2 {LOOKUP_MARKER}必须位于全部片段之后")
            lookup_body = text[lookup_position + len(LOOKUP_MARKER):].strip()
            actual_lookup: list[tuple[int, int, str]] = []
            if not lookup_body:
                errors.append(f"V2 {LOOKUP_MARKER}内容为空")
            for line in (line.strip() for line in lookup_body.splitlines() if line.strip()):
                lookup_match = LOOKUP_LINE_RE.fullmatch(line)
                if not lookup_match:
                    errors.append(f"V2 工作人员找图清单存在无法识别的映射行：{line}")
                    continue
                value = lookup_match.group(3).strip()
                if not ASSET_SLOT_RE.fullmatch(value):
                    errors.append(f"V2 工作人员找图清单槽位格式错误：{value}")
                actual_lookup.append((int(lookup_match.group(1)), int(lookup_match.group(2)), value))
            if actual_lookup != expected_lookup:
                errors.append("V2 工作人员找图清单与正文参考图片映射不一致")
    return errors, len(matches)


def validate(path: Path, legacy: bool = False) -> tuple[list[str], int]:
    return validate_text(path.read_text(encoding="utf-8-sig"), legacy=legacy)


def self_test() -> int:
    valid = """# 第1集视频提示词
【片段V1｜约8秒】
【参考图片】
@图片1=@人物P01-禹
@图片2=@场景S01-河岸
【风格】
历史写实，阴天土色，克制横移，湿土吸光。
【视频提示词】
禹从木桩左侧迈近半步，右手触到湿绳后收回；摄影机从右后方横移半个身位，在他看向河面时停住。
【对白与声音】
无对白。河声在右后方持续，手触湿绳时有短促纤维摩擦声。
【负面提示词】
禁止字幕、水印和标题；禁止擅自添加上游剧本与导演稿没有确认的人物、道具、对白与效果；保留导演批准的远处劳作人影和环境声；禁止身份漂移、肢体穿插和镜头瞬移。
【结束状态】
禹右手收在胸前，视线落向河面，河声持续。
【工作人员找图清单】
片段V1｜@图片1=@人物P01-禹
片段V1｜@图片2=@场景S01-河岸
"""
    missing_style = valid.replace("【风格】\n历史写实，阴天土色，克制横移，湿土吸光。\n", "")
    empty_modules = valid.replace("历史写实，阴天土色，克制横移，湿土吸光。", "").replace(
        "禹从木桩左侧迈近半步，右手触到湿绳后收回；摄影机从右后方横移半个身位，在他看向河面时停住。",
        "",
    ).replace(
        "无对白。河声在右后方持续，手触湿绳时有短促纤维摩擦声。",
        "",
    ).replace("禹右手收在胸前，视线落向河面，河声持续。", "")
    empty_end_before_lookup = valid.replace("禹右手收在胸前，视线落向河面，河声持续。", "")
    no_lookup = valid.split("【工作人员找图清单】", 1)[0]
    mismatched_lookup = valid.replace("片段V1｜@图片2=@场景S01-河岸", "片段V1｜@图片2=@场景S02-别处")
    invalid_slot = valid.replace("@图片1=@人物P01-禹", "@图片1=@人物S01-禹")
    malformed_ref = valid.replace("@图片2=@场景S01-河岸\n【风格】", "@图片2 这是一条坏映射\n【风格】")
    legacy = valid.replace("@图片1=@人物P01-禹", "@图片1=禹人物参考图").replace(
        "@图片2=@场景S01-河岸", "@图片2=河岸场景参考图"
    )
    with tempfile.TemporaryDirectory() as tmp:
        ok_path = Path(tmp) / "ok.md"
        missing_path = Path(tmp) / "missing.md"
        empty_path = Path(tmp) / "empty.md"
        empty_end_path = Path(tmp) / "empty-end.md"
        legacy_path = Path(tmp) / "legacy.md"
        no_lookup_path = Path(tmp) / "no-lookup.md"
        mismatch_path = Path(tmp) / "mismatch.md"
        invalid_slot_path = Path(tmp) / "invalid-slot.md"
        malformed_ref_path = Path(tmp) / "malformed-ref.md"
        ok_path.write_text(valid, encoding="utf-8-sig")
        missing_path.write_text(missing_style, encoding="utf-8-sig")
        empty_path.write_text(empty_modules, encoding="utf-8-sig")
        empty_end_path.write_text(empty_end_before_lookup, encoding="utf-8-sig")
        legacy_path.write_text(legacy, encoding="utf-8-sig")
        no_lookup_path.write_text(no_lookup, encoding="utf-8-sig")
        mismatch_path.write_text(mismatched_lookup, encoding="utf-8-sig")
        invalid_slot_path.write_text(invalid_slot, encoding="utf-8-sig")
        malformed_ref_path.write_text(malformed_ref, encoding="utf-8-sig")
        ok_errors, ok_count = validate(ok_path)
        missing_errors, _ = validate(missing_path)
        empty_errors, _ = validate(empty_path)
        empty_end_errors, _ = validate(empty_end_path)
        legacy_as_new_errors, _ = validate(legacy_path)
        legacy_errors, legacy_count = validate(legacy_path, legacy=True)
        no_lookup_errors, _ = validate(no_lookup_path)
        mismatch_errors, _ = validate(mismatch_path)
        invalid_slot_errors, _ = validate(invalid_slot_path)
        malformed_ref_errors, _ = validate(malformed_ref_path)
    if ok_errors or ok_count != 1:
        print("SELF-TEST FAIL: valid sample rejected")
        print("\n".join(ok_errors))
        return 1
    if not any("【风格】" in error for error in missing_errors):
        print("SELF-TEST FAIL: missing style module accepted")
        print("\n".join(missing_errors))
        return 1
    required_empty_labels = ("风格模块内容为空", "视频提示词模块内容为空", "对白与声音模块内容为空", "结束状态模块内容为空")
    if not all(any(label in error for error in empty_errors) for label in required_empty_labels):
        print("SELF-TEST FAIL: empty required module accepted")
        print("\n".join(empty_errors))
        return 1
    if not any("结束状态模块内容为空" in error for error in empty_end_errors):
        print("SELF-TEST FAIL: empty ending before lookup list accepted")
        print("\n".join(empty_end_errors))
        return 1
    if not any("未绑定稳定资产槽位" in error for error in legacy_as_new_errors):
        print("SELF-TEST FAIL: legacy mapping accepted as new contract")
        print("\n".join(legacy_as_new_errors))
        return 1
    if legacy_errors or legacy_count != 1:
        print("SELF-TEST FAIL: valid legacy mapping rejected in legacy mode")
        print("\n".join(legacy_errors))
        return 1
    if not any("找图清单" in error for error in no_lookup_errors):
        print("SELF-TEST FAIL: missing lookup list accepted")
        print("\n".join(no_lookup_errors))
        return 1
    if not any("找图清单与正文" in error for error in mismatch_errors):
        print("SELF-TEST FAIL: mismatched lookup list accepted")
        print("\n".join(mismatch_errors))
        return 1
    if not any("未绑定稳定资产槽位" in error for error in invalid_slot_errors):
        print("SELF-TEST FAIL: wrong slot type prefix accepted")
        print("\n".join(invalid_slot_errors))
        return 1
    if not any("无法识别的参考图片映射行" in error for error in malformed_ref_errors):
        print("SELF-TEST FAIL: malformed reference line accepted")
        print("\n".join(malformed_ref_errors))
        return 1
    print("SELF-TEST PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="按稳定资产槽位启用以前的旧参考图映射检查")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.path is None:
        parser.error("请提供视频提示词路径，或使用 --self-test")
    if not args.path.is_file():
        print(f"FAIL: 文件不存在：{args.path}")
        return 2
    try:
        errors, segment_count = validate(args.path, legacy=args.legacy)
    except UnicodeError as exc:
        print(f"FAIL: 文件编码错误：{exc}")
        return 2
    if errors:
        limit = 12
        for error in errors[:limit]:
            print(f"FAIL: {error}")
        if len(errors) > limit:
            print(f"FAIL: 另有{len(errors) - limit}项同类问题。")
        return 1
    contract = "旧合同（未迁移）" if args.legacy else "当前合同"
    print(f"PASS: {segment_count}个片段；每段六模块非空；参考图编号闭合；{contract}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
