# 历史与反馈数据格式

## 文件位置

默认 `history.jsonl`，位于项目根目录。每行一个 JSON 对象，追加写入。

该文件仅保存在本地，不上传、不包含任何个人信息。建议加入 `.gitignore`。

## 反馈记录

由 `scripts/apply_feedback.py` 或 HTML 报告中的反馈按钮产生：

```json
{"type": "feedback", "plan_id": "8a681e54d637", "tier": "generous", "result": "over", "result_text": "有剩余", "note": "一个人吃，剩下两根蛋满分", "ts": "2026-10-10T16:53:10+08:00"}
```

| 字段 | 说明 |
|---|---|
| `type` | 固定为 `feedback` |
| `plan_id` | 对应 `plan.json` 的 `plan_id` |
| `tier` | `conservative` / `fit` / `generous` |
| `result` | `under` 没吃够 / `fit` 刚好 / `over` 有剩余 |
| `result_text` | 中文说明 |
| `note` | 可选备注，不要填写个人信息 |
| `ts` | ISO 8601 本地时间 |

## 订单记录（可选）

记录 `order-list` 返回的历史订单摘要，用于统计「实际点了多少、剩了多少」。

只保存订单号、时间、餐品编码与数量，不要保存收货人、手机号、地址。

```json
{"type": "order", "order_id": "20261010xxxx", "ts": "2026-10-10T12:31:00+08:00", "items": [{"code": "9900013301", "qty": 1}], "kcal": 700, "price": 33.0}
```

## 系数推导

引擎读取所有 `type=feedback` 的记录：

- `under`：`factor × 1.06`
- `over`：`factor × 0.94`
- `fit`：不变

系数初始 1.00，区间 [0.75, 1.35]。样本数会显示在报告中，样本为 0 时提示「首次使用，按通用基准估算」。
