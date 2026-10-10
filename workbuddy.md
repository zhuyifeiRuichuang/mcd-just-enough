# workbuddy.md

> 本文件为使用腾讯 WorkBuddy 开发本项目的对话上下文记录，用于核验 WorkBuddy 专项奖励条件。
> 由 WorkBuddy 会话上下文整理而成。

## 项目

- 名称：麦麦刚刚好（mcd-just-enough）
- 仓库：待创建（个人 GitHub 账户公开仓库）
- 定位：基于麦当劳官方 MCP 的份量决策 Skill
- 开发环境：腾讯 WorkBuddy（Agent 模式）

---

## 一、需求起点

用户提出：分析麦当劳程序员创意开发大赛活动要求与限制，梳理已提交 Skill 的类型分布，并给出「别人没做的原创方向」与「整合已有 Skill 的方向」建议。

## 二、调研过程（WorkBuddy 完成）

1. 读取活动仓库 `M-China/mcd-developer-innovation-challenge` 的 `README.md`、`activityGuidelines.md`、`CONTEST_DECLARATION.md`、`RANKING.md`
2. 通过 GitHub API 抓取全部 Issues（截至 2026-10-10 共 273 条，去重后约 226 个作品）
3. 按一级与二级类型分类统计，识别拥挤赛道与空白赛道
4. 读取 `M-China/mcd-mcp-server` 工具表，确认实际可用工具为 34 个
5. 核对活动限制：中国大陆居民、Public 仓库、创建时间窗口、必须真实调用 MCP、Issue 正文不超过 1000 字且不带图片、同一账号仅 Star 最高的项目进榜

关键发现：

- 省钱与优惠券组合、营养配餐、多目标优化、人格测试与年度报告、积分到期管理均已高度拥挤
- 反浪费与适量点餐方向为 **0 个作品**
- `list-nutrition-foods`、`query-meal-detail`、`order-list` 三个能力可以组合成真正的份量引擎，但几乎无人用于该方向

## 三、决策过程（grill-me 逐分支确认）

| 决策点 | 选项 | 用户选择 |
|---|---|---|
| 参赛目标 | A 冲榜 / B 技术深度 / C 长期实用 | **A** |
| 主路线 | A 原创反浪费 / B 整合家庭关怀 | **A** |
| 目标人群 | A 个人小份 / B 家庭照护 / C 团餐 | **A** |
| 范围 | A 只读+核价停在付款前 / B 完整下单 / C 报告型 | **A** |
| 命名 | A 麦麦刚刚好 / B 麦麦不浪费 / C 麦麦份量官 | **A** |
| 引擎 | A 基础 / B 完整 / C 极简 | **B** |
| 演示 | A 纯真实 / B 真实优先+样例回退 / C 纯离线 | **B** |
| 输出 | A 对话+Markdown / B HTML 报告 / AB 两者都要 | **AB** |

## 四、实现过程（WorkBuddy 生成代码）

生成的文件：

1. `SKILL.md`：Skill 入口，九步标准工作流与硬约束
2. `scripts/plan_just_enough.py`：份量规划引擎
3. `scripts/build_report.py`：单文件 HTML 报告生成器
4. `scripts/apply_feedback.py`：餐后反馈写入
5. `examples/sample_menu.json`：离线演示样例菜单
6. `references/portion-model.md`、`references/mcp-tools.md`、`references/history-format.md`
7. `README.md`、`MCP_INTEGRATION.md`、`CONTEST_DECLARATION.md`、`mcp-config.example.json`

引擎调优过程中修正的问题：

- 饱腹单位与能量目标量纲不一致，导致结果退化成「越便宜越好」→ 引入 `SATIETY_PER_KCAL` 换算系数
- 组合枚举被 20000 条上限截断，导致两人场景选不出足够份量 → 改为「全量单品与双品 + 贪心种子一步/两步变异」
- 同一餐品被拆成多条展示（如「巨无霸×1 + 巨无霸×2」）→ 输出前按编码合并
- 三档可能重复 → 改为先锁定「刚好」档，再在其上下方分别取最优

## 五、验证记录

| 场景 | 命令 | 结果 |
|---|---|---|
| 1 人 · 正常 · 独食 · 堂食 · 40 元 | `--people 1 --appetite normal --scene solo --dining dine_in --budget 40` | 保守 470 kcal / 刚好 600 kcal / 丰盛 730 kcal |
| 2 人 · 正常 · 同行 · 堂食 · 80 元 | `--people 2 --appetite normal --scene pair --dining dine_in --budget 80` | 保守 980 / 刚好 1140 / 丰盛 1230 |
| 2 人 · 大食量 · 带娃 · 堂食 · 90 元 | `--people 2 --appetite heavy --scene family --dining dine_in --budget 90` | 保守 1070 / 刚好 1400 / 丰盛 1570 |
| 1 人 · 小食量 · 夜宵 · 外带 · 30 元 | `--people 1 --appetite light --scene night --dining takeout --budget 30` | 保守 340 / 刚好 430 / 丰盛 520 |

反馈闭环验证：

```
python scripts/apply_feedback.py --history history.jsonl --plan-id <id> --result over
→ 反馈已写入，下次会略微下调份量建议
→ 再次规划：feedback_factor 0.94，胃口线 700 → 658 kcal
```

报告生成验证：

```
python scripts/build_report.py --plan demo_plan.json --store "样例门店（离线演示）" --out demo_report.html
→ 报告已生成（单文件，内联 CSS/JS，无外部依赖）
```

## 六、后续待办

- 创建公开 GitHub 仓库并推送
- 用真实 MCP Token 跑通一次真实门店取数与核价，替换演示数据
- 在活动仓库提交报名 Issue（正文不超过 1000 字，不带图片）
