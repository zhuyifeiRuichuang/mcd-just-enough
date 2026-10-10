# workbuddy.md

> 本文件为使用腾讯 WorkBuddy 开发本项目的对话上下文记录，用于核验 WorkBuddy 专项奖励条件。
> 由 WorkBuddy 会话上下文整理而成。

## 项目

- 名称：麦麦刚刚好（mcd-just-enough）
- 仓库：https://github.com/zhuyifeiRuichuang/mcd-just-enough
- 定位：基于麦当劳官方 MCP 的适量点餐与反浪费决策 Skill
- 开发环境：腾讯 WorkBuddy（Agent 模式）

---

## 一、需求起点

用户提出：分析麦当劳程序员创意开发大赛活动要求与限制，梳理已提交 Skill 的类型分布，并给出「别人没做的原创方向」与「整合已有 Skill 的方向」建议。

## 二、调研过程（WorkBuddy 完成）

1. 读取活动仓库 `M-China/mcd-developer-innovation-challenge` 的 `README.md`、`activityGuidelines.md`、`CONTEST_DECLARATION.md`
2. 通过 GitHub API 抓取全部 Issues（截至 2026-10-10 共 273 条，去重后约 226 个作品）
3. 按一级与二级类型分类统计，识别拥挤赛道与空白赛道
4. 读取 `M-China/mcd-mcp-server` 工具表，并实测 `tools/list` 确认可用工具为 **35 个**
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
2. `scripts/mcd_mcp_client.py`：麦当劳 MCP Streamable HTTP 客户端（纯标准库）
3. `scripts/refine_combos.py`：套餐拆解，累加真实热量
4. `scripts/plan_just_enough.py`：份量规划引擎
5. `scripts/check_price.py`：官方核价
6. `scripts/build_report.py`：单文件 HTML 报告生成器
7. `scripts/apply_feedback.py`：餐后反馈写入
8. `examples/sample_menu.json`、`examples/real_*.json`：演示数据 + 真实取数快照
9. `references/portion-model.md`、`references/mcp-tools.md`、`references/history-format.md`
10. `README.md`、`MCP_INTEGRATION.md`、`CONTEST_DECLARATION.md`、`mcp-config.example.json`

引擎调优过程中修正的问题：

- 饱腹单位与能量目标量纲不一致，导致结果退化成「越便宜越好」→ 引入 `SATIETY_PER_KCAL` 换算系数
- 组合枚举被条数上限截断，两人场景选不出足够份量 → 改为「全量单品与双品 + 贪心种子一步/两步变异」
- 同一餐品被拆成多条展示（如「巨无霸×1 + 巨无霸×2」）→ 输出前按编码合并
- 三档可能重复 → 先锁定「刚好」档，再在其上下方分别取最优
- 丰盛档曾把已有饮品加量凑数 → 改为按「缺口」挑选最贴合的小食或甜品
- 营养估算项与真实数据混排 → 增加估算惩罚，并在结果中显式标注

## 五、真实 MCP 验证记录

| 步骤 | Tool | 结果 |
|---|---|---|
| 连通性 | `initialize` | `mcd-mcp 1.0.0`，协议 `2025-06-18` |
| 工具发现 | `tools/list` | 35 个工具 |
| 门店定位 | `query-nearby-stores` | 济南 5 家门店，取 `storeCode=3350050` |
| 菜单取数 | `query-meals` | 87 个在售餐品，12 个分类 |
| 营养取数 | `list-nutrition-foods` | 160 条餐品营养 |
| 套餐拆解 | `query-meal-detail` | 10 个套餐按默认组成累加营养 |
| 历史订单 | `order-list` | 近期订单含商品明细，可用于个人食量基线 |
| 官方核价 | `calculate-price` | 保守 ¥31.0 / 刚好 ¥37.5 / 丰盛 ¥45.0 |

实测样例场景（1 人 · 正常食量 · 独食 · 堂食 · 预算 45 元）：

| 档位 | 组合 | 能量 | 金额 |
|---|---|---|---|
| 保守 | 麦香鸡 + 纯牛奶 | 498 kcal | ¥31.0 |
| 刚好 | 麦辣鸡腿汉堡 + 纯牛奶 | 614 kcal | ¥37.5 |
| 丰盛 | 芝士安格斯厚牛堡 + 雪碧 | 801 kcal | ¥45.0（浪费约 9%） |

官方核价与引擎按菜单价的估算完全一致，说明价格链路可信。

反馈闭环验证：

```
python scripts/apply_feedback.py --history history.jsonl --plan-id <id> --result over
→ 反馈已写入，下次会略微下调份量建议
→ 再次规划：feedback_factor 0.94，胃口线 700 → 658 kcal
```

## 六、WorkBuddy 在本项目中的作用

- 完成活动规则与赛道调研，用逐分支决策锁定方向
- 生成全部代码：MCP 客户端、套餐拆解器、份量引擎、核价脚本、报告生成器
- 使用真实 MCP Token 完成端到端联调，并把真实返回解析为引擎可消费的数据结构
- 生成参赛所需文档：`README.md`、`MCP_INTEGRATION.md`、`workbuddy.md`、`CONTEST_DECLARATION.md`
- 创建公开仓库、配置代理与推送（含冲突处理）

## 七、后续待办

- 在活动仓库提交报名 Issue（正文不超过 1000 字，不带图片）
- 持续迭代：更多门店与场景的实测数据
