---
name: mcd-just-enough
description: 麦当劳「刚刚好」点餐决策 Skill。基于麦当劳官方 MCP，根据人数、食量、场景、预算与历史反馈，计算真正合适的份量，输出保守/刚好/丰盛三档方案，给出份量条、饱腹评分、预估浪费率与浪费金额，并用 calculate-price 做官方核价，停在付款前由用户确认。适用于“一个人吃麦当劳点多少”“两个人别点多了”“怕剩”“想吃饱又不浪费”“带娃怎么点”等需求。
---

# 麦麦刚刚好 / McJustEnough

点麦当劳最常见的浪费不是点贵了，而是**点多了**：单人套餐吃不完、双人点三件套剩一堆、给孩子点成人份、加班夜宵怕撑又怕饿。

本 Skill 不追求“最便宜”，也不追求“热量最低”，而是回答一个没人回答的问题：

> 这一顿，到底点多少才刚刚好？

## 何时使用

- 用户说：点多少合适、怕点多了、两个人的量、一个人吃不完、别浪费、带娃怎么点、夜宵别太撑
- 用户给出人数、场景、预算，希望直接得到可执行方案
- 用户想知道自己历史上是不是经常点多吃不完

## 前置条件

- 需要麦当劳中国 MCP Token：https://open.mcd.cn/mcp
- 在 MCP Client 中配置 `mcd-mcp`（参考 `mcp-config.example.json`，Token 通过环境变量占位符注入）
- 无 Token 时可用内置样例数据跑通全流程（演示模式），但参赛与真实使用必须走真实 MCP

## 核心原则

1. **份量优先，价格第二**：先算清吃不吃得完，再算钱。
2. **真实数据**：菜单、营养、券、价格一律来自麦当劳官方 MCP，不臆造。
3. **停在付款前**：只读建议 + 官方核价，不代替用户下单，不触碰支付。
4. **会学习**：餐后一句反馈（没吃够 / 刚好 / 有剩余）即可修正个人份量系数。
5. **不浪费**：预估浪费率与浪费金额是主输出，不是附加信息。
6. **数据可信度透明**：营养表未覆盖的新品按同类均值估算，并在结果中显式标注。

## 标准工作流

### 第 1 步：收集 5 个入参（缺哪个问哪个，一次问完）

| 参数 | 取值 | 默认值 |
|---|---|---|
| `people` | 人数 | 1 |
| `appetite` | `light` 小食量 / `normal` 正常 / `heavy` 大食量 | `normal` |
| `scene` | `solo` 独食 / `pair` 两人 / `family` 带娃 / `work` 加班 / `night` 夜宵 | `solo` |
| `dining` | `dine_in` 堂食 / `takeout` 外带 / `delivery` 麦乐送 / `drive_thru` 得来速 | `dine_in` |
| `budget` | 预算上限，元；0 表示不限 | 0 |

同时问忌口（如不要酸瓜、不要辣、不要冰）与偏好（如想喝热饮、想吃牛肉）。

### 第 2 步：定位门店

```bash
python scripts/mcd_mcp_client.py fetch-stores --city 济南 --keyword 济南 --out stores.json
```

- 堂食 / 得来速：`query-nearby-stores`（`beType=1` 到店自提，`beType=5` 得来速）
- 麦乐送：`delivery-query-addresses` → `delivery-query-stores`
- 用 `now-time-info` 取当前时间，判断早餐 / 正餐 / 夜宵时段

记录 `storeCode`；到店场景不传 `beCode`，外送场景需要传。

### 第 3 步：取菜单与营养

```bash
python scripts/mcd_mcp_client.py fetch-nutrition --out nutrition.json
python scripts/mcd_mcp_client.py fetch-menu --store-code <storeCode> --out candidates.json
```

- `query-meals` 取在售菜单（分类、餐品编码、价格）
- `list-nutrition-foods` 取真实营养数据（能量、蛋白质、脂肪、碳水、钠、钙）
- 套餐在营养表里没有同名条目，用 `query-meal-detail` 拆解后累加：

```bash
python scripts/refine_combos.py --candidates candidates.json \
  --nutrition nutrition.json --store-code <storeCode> --out candidates_refined.json
```

### 第 4 步：读历史，建立个人份量系数

- `order-list` 取近期到店/外送历史订单
- 读取本地 `history.jsonl`（格式见 `references/history-format.md`）

若历史或反馈为空，系数为 1.0，并在报告中标注“首次使用，按通用基准估算”。

### 第 5 步：调用份量引擎

```bash
python scripts/plan_just_enough.py \
  --people 1 --appetite normal --scene solo --dining dine_in --budget 45 \
  --candidates candidates_refined.json --nutrition nutrition.json \
  --data-source mcp --store "<门店名>" --out plan.json
```

无 Token 时改用内置样例：

```bash
python scripts/plan_just_enough.py \
  --people 2 --appetite normal --scene pair --dining dine_in --budget 80 \
  --candidates examples/sample_menu.json --data-source sample --out plan.json
```

引擎输出三档：保守 / 刚好 / 丰盛。计算逻辑见 `references/portion-model.md`。

### 第 6 步：官方核价

```bash
python scripts/check_price.py --plan plan.json --all-tiers \
  --store-code <storeCode> --out price.json
```

- `query-store-coupons` 取本店可用券；**券只认本店 `calculate-price` 的试算差值，不拿券包列表下结论**
- 未领券时可先 `available-coupons` 查看、再 `auto-bind-coupons` 一键领取（领取需用户同意）
- `calculate-price` 返回金额单位为分，脚本已换算为元

### 第 7 步：生成报告

```bash
python scripts/build_report.py --plan plan.json --price price.json \
  --store "<门店名>" --out report.html
```

生成单文件 HTML（内联 CSS/JS，无外部依赖），含三档方案对比、份量条、浪费预估、官方核价区块与反馈按钮。

同时在对话内输出 Markdown 精简建议卡：三档各 3 行（组合 / 份量条 / 价格与浪费预估）。

### 第 8 步：停在付款前

输出末尾必须包含：

> 以上是建议与官方核价结果，尚未下单。确认要下单请明确告诉我，我再调用 `create-order`。

**未经用户明确确认，绝不调用 `create-order`。**

### 第 9 步：餐后反馈闭环

用户吃完反馈一句即可：

```bash
python scripts/apply_feedback.py --history history.jsonl --plan-id <id> --result fit
```

`result` 取值：`under` 没吃够 / `fit` 刚好 / `over` 有剩余。

下次自动修正个人份量系数，形成真正的闭环。

## 输出要求

每档方案必须包含：

1. 组合清单（品名 + 份数 + 编码）
2. 份量条：`[====|====]` 形式，标出需求线与本档实际线
3. 饱腹评分与营养汇总（能量、蛋白质）
4. 预估浪费率与浪费金额
5. 官方核价结果（商品金额、优惠、应付总价）
6. 一句话理由：为什么这一档是“刚刚好”
7. 若组合中含营养估算项，注明“部分新品按同类均值估算”

## 硬约束

- 不得输出真实 Token、密钥、手机号、地址或其他个人信息
- 不得将麦当劳与其他品牌、产品进行价格或品质对比
- 不得给出医疗、营养治疗或疾病相关建议；营养数据仅用于份量估算
- 每次输出必须包含：非麦当劳官方产品、输出仅供参考、餐品与价格以官方实时结果为准
- 不得代替用户下单或支付
- 单 Token 每分钟不超过 600 次请求；批量拆解套餐时保持温和限速

## 文件说明

| 文件 | 作用 |
|---|---|
| `scripts/mcd_mcp_client.py` | 麦当劳 MCP Streamable HTTP 客户端（ping / tools-list / call / fetch-stores / fetch-menu / fetch-nutrition） |
| `scripts/refine_combos.py` | 用 `query-meal-detail` 拆解套餐，累加真实热量 |
| `scripts/plan_just_enough.py` | 份量规划引擎，输出三档方案 JSON |
| `scripts/check_price.py` | 用 `calculate-price` 对三档做官方核价 |
| `scripts/build_report.py` | 生成单文件 HTML 报告 |
| `scripts/apply_feedback.py` | 写入餐后反馈并更新份量系数 |
| `references/portion-model.md` | 份量与浪费模型说明 |
| `references/mcp-tools.md` | 麦当劳 MCP 工具清单与调用约束 |
| `references/history-format.md` | 历史与反馈数据格式 |
| `examples/sample_menu.json` | 离线演示样例菜单（仅供无 Token 演示） |
| `examples/real_*.json` | 真实接口取数快照，可离线复盘 |
