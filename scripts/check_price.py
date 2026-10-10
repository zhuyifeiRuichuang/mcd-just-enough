#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用麦当官方 MCP 的 calculate-price 对方案做真实核价。

引擎给出的金额是根据菜单价做的估算；真实金额要以 calculate-price 的结果为准
（含优惠、配送费与应付总价）。本脚本只做核价，不创建订单。

用法：
    python scripts/check_price.py --plan plan.json --tier fit \
        --store-code 3350050 --out price_fit.json
    python scripts/check_price.py --plan plan.json --all-tiers --store-code 3350050
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcd_mcp_client import McpError, call_tool, load_token, unwrap  # noqa: E402


def build_items(tier: dict) -> list:
    items = []
    for it in tier.get("items", []):
        code = it.get("code") or (it.get("codes") or [None])[0]
        if not code:
            continue
        items.append({"productCode": str(code), "quantity": int(it.get("qty", 1) or 1)})
    return items


def brief(result) -> dict:
    """从核价结果里挑出关键金额字段。

    麦当劳返回金额单位为「分」，这里统一换算成元。
    """
    if not isinstance(result, dict):
        return {"fields": {}, "raw": result}

    def yuan(value):
        if value is None:
            return None
        try:
            return round(float(value) / 100.0, 2)
        except (TypeError, ValueError):
            return None

    def pick(keys):
        for k in keys:
            if k in result:
                return result[k]
        return None

    return {
        "fields": {
            "goods": yuan(pick(("productPrice", "goodsAmount", "productAmount"))),
            "original": yuan(pick(("productOriginalPrice", "originalPrice"))),
            "discount": yuan(pick(("discount", "discountAmount", "promotionAmount"))),
            "delivery": yuan(pick(("deliveryFee", "shippingFee", "freight"))),
            "payable": yuan(pick(("price", "payAmount", "payableAmount", "totalAmount"))),
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="用官方 calculate-price 真实核价")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--tier", default="fit",
                        choices=["conservative", "fit", "generous"])
    parser.add_argument("--all-tiers", action="store_true", help="核价全部三档")
    parser.add_argument("--store-code", required=True)
    parser.add_argument("--order-type", type=int, default=1)
    parser.add_argument("--be-type", type=int, default=1)
    parser.add_argument("--be-code", default="")
    parser.add_argument("--need-tableware", action="store_true")
    parser.add_argument("--token", default="")
    parser.add_argument("--url", default="https://mcp.mcd.cn")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    token = load_token(args.token)
    if not token:
        print("缺少 MCP Token。", file=sys.stderr)
        return 2

    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    tiers = plan.get("tiers", [])
    want = [t["tier"] for t in tiers] if args.all_tiers else [args.tier]

    results = []
    for tier in tiers:
        if tier.get("tier") not in want:
            continue
        items = build_items(tier)
        if not items:
            continue
        params = {
            "storeCode": args.store_code,
            "orderType": args.order_type,
            "beType": args.be_type,
            "items": items,
            "needTableware": bool(args.need_tableware),
        }
        if args.be_code:
            params["beCode"] = args.be_code
        try:
            raw = unwrap(call_tool("calculate-price", params, token, args.url))
        except McpError as exc:
            print("[%s] 核价失败：%s" % (tier.get("label"), exc), file=sys.stderr)
            continue
        entry = {
            "tier": tier.get("tier"),
            "label": tier.get("label"),
            "estimated_price": tier.get("price"),
            "items": items,
            "official": raw,
        }
        entry.update(brief(raw))
        results.append(entry)
        pay = entry["fields"].get("payable")
        print("%s：估算 ¥%s -> 官方核价 %s" % (
            tier.get("label"), tier.get("price"),
            ("¥%s" % pay) if pay is not None else "（见 official 字段）"))

    payload = {
        "store_code": args.store_code,
        "order_type": args.order_type,
        "be_type": args.be_type,
        "source_tool": "calculate-price",
        "checked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("已写入：%s" % os.path.abspath(args.out))
    else:
        print(text)
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
