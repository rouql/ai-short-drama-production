# 🎬 AI Short Drama Production

**V20 — Feature-Frozen AI Short-Drama Production Skill** · V20 封版 · AI 短剧量产型生产技能

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-V20-important.svg)](SKILL.md)

> 这不是格式模板，而是一套**量产型创作 Skill**：完成或修复 AI 短剧的故事架构、正常短剧剧本、
> 导演分解、全剧资产生图提示词和分集视频提示词，采用分阶段专业创作与轻量质量门禁。
>
> This is not a format template — it is a **mass-production creation skill** that completes or
> repairs story architecture, normal short-drama screenplays, director breakdowns, full-series
> asset image prompts and episode video prompts, with staged professional creation and a
> lightweight quality gate.

**V20 封版声明 / Frozen Status**：本版本已完成设计并封版，不再修改（"再也不改 Skill 了"）。

---

## 🔗 Related Project / 相关项目

本仓库是 **V20 封版的精简量产版**；想要完整的多智能体全家桶版本（故事/人物/剧本/QA/营销等
20+ Agent、11 条工作流、记忆与知识图谱）？

→ [**AI-Drama-Skill**](https://github.com/rouql/AI-Drama-Skill)

This is the lean, feature-frozen V20 production skill. For the full multi-agent all-in-one
version (20+ agents, 11 workflows, memory & knowledge graph), see
[AI-Drama-Skill](https://github.com/rouql/AI-Drama-Skill).

## ✨ Core Features / 核心特性

| Feature | 说明 / Description |
|---|---|
| 双运行模式 | **生产模式**（默认，只处理项目产物）与**维护模式**（仅用户明确要求时修改 Skill 本身） |
| 分阶段路由 | 按任务加载对应阶段参考：故事 → 剧本 → 导演 → 资产 → 视频，不一次加载全部 |
| 轻量发布门 | 强制四步闭环：生成一次 → 静默检查 → 定向修复 → 再检查；通过才交付 |
| 硬性红线 | 9 条不可删除红线：正常剧本格式、因果驱动、无字数配额、阶段职责分离等 |
| 批量效率 | 长剧先验容量再批量写、逐单元流式检查、不产生无价值的副文件 |
| 校验脚本 | 4 个确定性 Python 校验器，机械拦截格式与闭合错误 |

## 🗺 Production Stages / 生产阶段

```
项目事实基准 → 故事架构与分集大纲 → 正常短剧剧本 → 导演分解 → 全剧资产提示词 → 分集视频提示词
Project Facts → Story Architecture → Screenplay → Director Breakdown → Asset Prompts → Episode Video Prompts
```

每阶段有对应参考文件（`references/`），**强制发布门**（`quality-gate.md`）约束所有阶段：
- `G1 范围` · `G2 忠实` · `G3 连续` · `G4 可用`（通用检查）
- `N1 因果` · `N2 变化` · `N3 情绪`（叙事型阶段追加）

## 📁 Project Structure / 目录结构

```
ai-short-drama-production/
├── SKILL.md                        # 技能入口：模式、路由、红线、发布门、批量效率
├── references/
│   ├── quality-gate.md             # 强制轻量发布门（所有阶段必读）
│   ├── story.md                    # 故事架构、分集大纲、金钩、情绪线
│   ├── script.md                   # 正常短剧剧本、对白
│   ├── director.md                 # 导演分解、镜头设计、表演调度
│   ├── assets.md                   # 资产提取、角色定妆、生图提示词
│   ├── video.md                    # 分集视频提示词、对白口型
│   └── historical-production.md    # 历史题材/地方文化题材专用
└── scripts/
    ├── validate_script.py          # 剧本结构校验
    ├── validate_director.py        # 导演包校验
    ├── validate_asset_prompts.py   # 资产生图提示词校验
    └── validate_video.py           # 视频提示词校验
```

## 🚀 Quick Start / 快速开始

1. 加载 `SKILL.md`，确定运行模式（默认生产模式）
2. 每次任务固定读取 `references/quality-gate.md`，再按阶段读取对应参考文件
3. 创作完成后执行强制发布门：生成 → 静默检查 → 定向修复 → 再检查
4. 可用校验脚本辅助机械检查（Python 3）：

```bash
python scripts/validate_script.py <剧本文件>
python scripts/validate_director.py <导演文件>
python scripts/validate_asset_prompts.py <资产提示词文件>
python scripts/validate_video.py <视频提示词文件>
```

## 🛡 Non-Negotiable Red Lines / 硬性红线（节选）

1. 正式剧本使用**正常短剧剧本格式**，不能写成逐秒分镜或字段堆砌
2. 每集必须有具体事件、人物目标、有效阻力、主动行动、状态变化与因果结尾
3. 不设置正文总字数、场景数、对白数等配额——质量由因果、节奏、变化、人物和可制作性判断
4. 导演阶段负责把剧本转化为镜头、表演、光线、声音，不得反塞回剧本
5. 资产阶段只生成生图提示词，视频阶段只生成视频提示词，**不调用图片/视频生成工具**
6. 任何正文、导演包或提示词交付前必须执行发布门，不能因赶时间或批量生产跳过

## 📄 License / 许可

本项目基于 [MIT License](LICENSE) 开源。

---

*Made for AI short-drama mass production · 为 AI 短剧量产而作*