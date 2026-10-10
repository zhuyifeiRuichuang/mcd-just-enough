# 更新日志

本项目所有版本均遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：主版本号.次版本号.修订号。

## v1.1.0（2026-10-10）

接入真实麦当劳 MCP，完成端到端验证。Skill 从「离线可演示」升级为「真实可用」。

### 新增

- `scripts/mcd_mcp_client.py`：麦当劳 MCP 客户端，纯标准库实现 Streamable HTTP 传输
  - 子命令：`ping` / `tools-list` / `call` / `fetch-stores` / `fetch-menu` / `fetch-nutrition`
  - 自动解析工具返回的「字段说明 + JSON」混合文本
  - 专门解析 `list-nutrition-foods` 返回的自定义文本表
- `scripts/refine_combos.py`：套餐拆解器，用 `query-meal-detail` 拆解套餐默认组成并累加真实营养数据
- `scripts/check_price.py`：官方核价脚本，用 `calculate-price` 对三档方案逐一核价，金额由分换算为元
- 单文件 HTML 报告新增「官方核价」区块，估算价与官方核价并列展示
- `references/mcp-tools.md` 更新为 `tools/list` 真实返回的 35 个工具清单，标注已用 / 预留 / 未使用
- 真实取数快照入库：`examples/real_stores_jinan.json`、`real_nutrition.json`、`real_menu_3350050.json`、`real_plan.json`、`real_price.json`

### 修正

- 套餐不再被当成单一主食，改为主食 + 小食 + 饮品组合，避免在三档方案上重复加饮料
- 营养数据为估算的餐品在评分中降权，优先选用真实营养数据可匹配的餐品
- 「丰盛」档改为按热量缺口挑选小食或甜品，不再通过把饮品加量来凑数
- `calculate-price` 金额单位由分换算为元后再展示

### 变更

- `SKILL.md` 工作流改为真实 MCP 调用链，补充工具入参、返回结构与降级策略
- `MCP_INTEGRATION.md` 补充真实调用证据与返回片段
- `workbuddy.md` 同步真实验证结果

---

## v1.0.0（2026-10-10）

首个可用版本：份量引擎、三档方案、浪费预估、反馈闭环与单文件 HTML 报告。

### 新增

- `scripts/plan_just_enough.py`：份量规划引擎
  - 以真实营养数据计算饱腹贡献，而非只看热量
  - 场景因子：独食 / 同行 / 带娃 / 加班 / 夜宵
  - 输出保守 / 刚好 / 丰盛三档，并给出预估浪费率与浪费金额
- `scripts/build_report.py`：单文件 HTML 报告生成器，内联 CSS/JS，无外部依赖
- `scripts/apply_feedback.py`：餐后反馈闭环，一句「没吃够 / 刚好 / 有剩余」即可修正个人份量系数
- `examples/sample_menu.json`：离线演示样例菜单，无 Token 也能跑通全流程
- `references/portion-model.md`：份量与浪费模型，含全部系数
- `references/history-format.md`：历史与反馈数据格式
- 参赛材料：`README.md`、`CONTEST_DECLARATION.md`、`MCP_INTEGRATION.md`、`mcp-config.example.json`、`workbuddy.md`
