# 麦当劳 MCP 工具清单与调用约束

来源：麦当劳 MCP Server 官方仓库 `M-China/mcd-mcp-server` 工具表。
接入地址 `https://mcp.mcd.cn`，Streamable HTTP，请求头 `Authorization: Bearer <TOKEN>`。

## 限流与错误码

- 每个 Token 每分钟最多 600 次请求，超限返回 429
- 401 表示 Token 无效、过期或未提供
- 令牌只通过环境变量占位符注入，代码中不得出现真实 Token

## 工具分组

| 分组 | 工具 | 本项目是否使用 | 说明 |
|---|---|---|---|
| 门店与地址 | `query-nearby-stores`、`delivery-query-addresses`、`delivery-query-stores`、`delivery-create-address` | 使用 | 堂食/得来速走 `query-nearby-stores`；麦乐送先取地址再取可配送门店 |
| 菜单 | `query-meals`、`query-meal-detail`、`list-nutrition-foods`、`query-meal-assistance` | 使用 | 菜单、套餐组成与可替换项、真实营养数据 |
| 价格 | `calculate-price` | 使用 | 官方核价，含商品金额、配送费、优惠金额、应付总价 |
| 订单 | `create-order`、`cancel-order`、`query-order`、`order-list` | 使用 | 当前范围只读到核价；`order-list` 用于读历史订单；`create-order` 仅在用户明确确认后调用 |
| 优惠券 | `available-coupons`、`auto-bind-coupons`、`query-my-coupons`、`query-store-coupons` | 使用 | 券只认本店试算差值，不拿券包下结论 |
| 积分与商城 | `query-my-account`、`mall-points-products`、`mall-product-detail`、`mall-create-order`、`mall-order-list`、`mall-order-detail` | 预留 | 后续可扩展为「用即将过期的积分补齐份量」 |
| 抽奖 | `query-lottery-info`、`draw-lottery`、`query-my-prizes` | 不使用 | 与份量目标无关 |
| 活动 | `campaign-calendar` | 预留 | 后续可判断活动期是否影响供应 |
| 时间 | `now-time-info` | 使用 | 判断早餐/正餐/夜宵时段 |
| 派对 | `query-party-city`、`query-party-store`、`query-partystore-date`、`query-partystore-session`、`party-order-create` | 不使用 | 属于派对预约场景，本项目聚焦日常点餐 |

## 标准调用链

```
now-time-info
  → query-nearby-stores / delivery-query-stores        取 storeCode
  → query-meals                                        取在售菜单与餐品编码
  → query-meal-detail                                  拆解套餐组成与可替换项
  → list-nutrition-foods                               取营养数据
  → order-list                                         读历史订单
  → [本地] plan_just_enough.py                          份量规划，输出三档
  → query-store-coupons                                取本店可用券
  → calculate-price                                    逐档核价
  → [本地] build_report.py                              生成 HTML 报告
  → 用户确认 → create-order                             仅在此步才下单
```

## 使用约束

1. **只读优先**：除用户明确授权外，只调用读取类工具。
2. **核价为准**：券的可用性以本店 `calculate-price` 试算差值判断，不以券包列表下结论。
3. **不触碰支付**：`create-order` 返回支付链接，必须由用户在官方渠道完成支付。
4. **不比较其他品牌**：不接入也不对比任何第三方平台价格。
5. **频控**：批量核价控制在每分钟 600 次以内，三档方案最多三次核价调用。
