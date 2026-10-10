# MCP 集成说明

## 一、使用的 MCP Server

| 项 | 内容 |
|---|---|
| Server | 麦当劳中国 MCP Server |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | `Authorization: Bearer ${MCD_MCP_TOKEN}`，Token 仅通过环境变量占位符注入 |
| 限流 | 每 Token 每分钟 600 次请求，超限返回 429 |
| 官方文档 | https://github.com/M-China/mcd-mcp-server |

## 二、使用的 Tool 与调用流程

### 完整调用链

```
now-time-info
  ↓ 判断当前处于早餐 / 正餐 / 夜宵时段
query-nearby-stores            （或 delivery-query-addresses → delivery-query-stores）
  ↓ 取得 storeCode
query-meals
  ↓ 取得在售菜单、分类与餐品编码
query-meal-detail
  ↓ 拆解套餐组成、轮次选配、可替换项与特调
list-nutrition-foods
  ↓ 取得能量、蛋白质、脂肪、碳水、钠、钙
order-list
  ↓ 取得近期历史订单，用于推算个人食量基线
[本地] scripts/plan_just_enough.py
  ↓ 份量规划，输出保守 / 刚好 / 丰盛三档
query-store-coupons
  ↓ 取得本店可用券
calculate-price
  ↓ 逐档官方核价，得到商品金额、优惠金额、应付总价
[本地] scripts/build_report.py
  ↓ 生成单文件 HTML 报告
用户明确确认 → create-order
```

### 逐个 Tool 的业务价值

| Tool | 在本项目中的作用 | 业务价值 |
|---|---|---|
| `now-time-info` | 判断时段 | 早餐、正餐、夜宵的合理份量差异很大，时段是份量模型的输入之一 |
| `query-nearby-stores` | 定位堂食/得来速门店 | 没有真实门店就无法取真实菜单，份量建议无从谈起 |
| `delivery-query-addresses` | 取外送地址 | 麦乐送场景的前置步骤 |
| `delivery-query-stores` | 取可配送门店 | 麦乐送场景的前置步骤 |
| `query-meals` | 取在售菜单 | 份量规划的候选集来源，避免推荐已下架餐品 |
| `query-meal-detail` | 拆解套餐 | 知道套餐里到底有什么，才能判断「一个人吃这个套餐会不会剩」 |
| `list-nutrition-foods` | 取营养数据 | 份量与饱腹计算的真实依据，不臆造热量 |
| `order-list` | 读历史订单 | 建立个人食量基线，让建议越用越准 |
| `query-store-coupons` | 取本店可用券 | 券只认本店试算差值，不以券包列表下结论 |
| `calculate-price` | 官方核价 | 三档方案的真实价格与优惠，避免本地估算失真 |
| `create-order` | 下单 | 仅在用户明确确认后调用，返回支付链接由用户完成支付 |

### 未使用的 Tool 及原因

| Tool | 原因 |
|---|---|
| `available-coupons` / `auto-bind-coupons` / `query-my-coupons` | 领券属于账户变更操作，需用户明确同意；本项目默认只用本店已可用券 |
| `query-my-account` / `mall-*` / `query-lottery-info` / `draw-lottery` / `query-my-prizes` | 积分与抽奖与份量目标无关，预留为后续扩展 |
| `campaign-calendar` | 预留用于判断活动期供应波动 |
| `query-party-city` / `query-party-store` / `query-partystore-date` / `query-partystore-session` / `party-order-create` | 派对预约场景，不属于日常点餐份量问题 |
| `cancel-order` / `query-order` | 当前范围为下单前决策，不涉及售后 |
| `query-meal-assistance` | 仅企业团餐场景使用 |

## 三、调用约束

1. **只读优先**：除用户明确授权外，只调用读取类工具。
2. **券以试算为准**：券的可用性以本店 `calculate-price` 的试算差值判断，不拿券包列表下结论。
3. **不触碰支付**：`create-order` 只负责生成订单与支付链接，支付由用户在官方渠道完成。
4. **频控**：三档方案最多三次 `calculate-price`，远低于 600 次/分钟的限制。
5. **不比较其他品牌**：不接入、不引用、不对比任何第三方平台价格。
6. **密钥安全**：Token 只存在于环境变量与用户本地 MCP 配置中，代码与提交材料里只有占位符。

## 四、真实调用证据

MCP_INTEGRATION 中记录的调用链已在开发过程中逐一验证：菜单取数、套餐拆解、营养取数、门店可用券查询与 `calculate-price` 核价均使用真实接口返回数据；`create-order` 仅在用户确认场景下调用。

离线演示模式（`--data-source sample`）使用 `examples/sample_menu.json`，仅用于无 Token 时展示引擎与报告效果，不代表真实接口数据。

## 五、业务价值总结

麦当劳 MCP 过去被大量用于「怎么更便宜」。本项目把它用在一个没人做过的方向：**怎么刚好吃完**。

- 对顾客：少花冤枉钱、少剩食物、吃得舒服
- 对麦当劳：减少食物浪费，与反浪费的社会导向一致
- 对开发者：展示了 MCP 不只是比价工具，营养数据、套餐拆解与历史订单可以组合成真正的决策引擎
