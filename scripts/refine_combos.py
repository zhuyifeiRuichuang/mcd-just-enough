#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""套餐热量拆解器。

query-meals 只给价格，套餐（如「麦辣鸡腿汉堡三件套」）在营养表里没有同名条目。
本脚本用 query-meal-detail 拿到套餐的默认组成（rounds[].choices[] 中 isDefault=1 的项），
再用 list-nutrition-foods 的营养表逐项累加，得到真实的热量、蛋白质与钠。

用法：
    python scripts/refine_combos.py --candidates candidates.json \
        --nutrition nutrition.json --store-code 3350050 --out candidates_refined.json

只处理未匹配到营养的套餐，单品直接跳过，调用次数可控（默认上限 40 次）。
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcd_mcp_client import (  # noqa: E402
    McpError, call_tool, load_token, match_nutrition, unwrap,
)

# 营养表里查不到的新品，按同类均值兜底：(kcal, protein, sodium)
CATEGORY_DEFAULT = {
    "main": (480.0, 24.0, 900.0),
    "combo": (760.0, 30.0, 1300.0),
    "side": (280.0, 6.0, 450.0),
    "dessert": (240.0, 4.0, 120.0),
    "drink": (130.0, 2.0, 30.0),
    "soup": (90.0, 3.0, 300.0),
    "other": (150.0, 3.0, 200.0),
}


def default_components(detail: dict) -> list:
    """取套餐默认组成（isDefault=1）。"""
    comps = []
    for rnd in (detail or {}).get("rounds") or []:
        for choice in rnd.get("choices") or []:
            if int(choice.get("isDefault", 0) or 0) != 1:
                continue
            qty = int(choice.get("quantity", 1) or 1)
            name = str(choice.get("name") or "").strip()
            if name:
                comps.append((name, qty))
    return comps


def main() -> int:
    parser = argparse.ArgumentParser(description="套餐热量拆解")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--nutrition", required=True)
    parser.add_argument("--store-code", required=True)
    parser.add_argument("--order-type", type=int, default=1)
    parser.add_argument("--be-type", type=int, default=1)
    parser.add_argument("--be-code", default="")
    parser.add_argument("--limit", type=int, default=40, help="最多拆解多少个套餐")
    parser.add_argument("--token", default="")
    parser.add_argument("--url", default="https://mcp.mcd.cn")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    token = load_token(args.token)
    if not token:
        print("缺少 MCP Token。", file=sys.stderr)
        return 2

    with open(args.candidates, encoding="utf-8") as fh:
        payload = json.load(fh)
    with open(args.nutrition, encoding="utf-8") as fh:
        nutrition_rows = json.load(fh).get("foods", [])
    by_name = {r["productName"]: r for r in nutrition_rows}

    cands = payload.get("candidates", [])
    targets = [c for c in cands if c.get("estimated") and c.get("category") == "combo"]
    print("待拆解套餐：%d（上限 %d）" % (len(targets), args.limit))

    refined = 0
    for cand in targets[:args.limit]:
        params = {"storeCode": args.store_code, "orderType": args.order_type,
                  "beType": args.be_type, "code": cand["code"]}
        if args.be_code:
            params["beCode"] = args.be_code
        try:
            detail = unwrap(call_tool("query-meal-detail", params, token, args.url))
        except McpError as exc:
            print("  跳过 %s：%s" % (cand["name"], exc))
            continue
        comps = default_components(detail if isinstance(detail, dict) else {})
        if not comps:
            continue
        kcal = protein = sodium = 0.0
        hit_count = 0
        names = []
        for name, qty in comps:
            row = match_nutrition(name, by_name)
            names.append("%s×%d" % (name, qty))
            if row:
                hit_count += 1
                kcal += row["kcal"] * qty
                protein += row["protein"] * qty
                sodium += row["sodium"] * qty
        if hit_count == 0:
            continue
        cand["kcal"] = round(kcal, 1)
        cand["protein"] = round(protein, 1)
        cand["sodium"] = round(sodium, 1)
        cand["estimated"] = hit_count < len(comps)
        cand["nutrition_source"] = "query-meal-detail + list-nutrition-foods"
        cand["components"] = names
        refined += 1
        time.sleep(0.12)  # 温和限速，远离 600 次/分钟上限

    # 兜底：营养表查不到的新品，按同类均值估算并显式标注
    for cand in cands:
        if cand.get("estimated") and not cand.get("kcal"):
            kcal, protein, sodium = CATEGORY_DEFAULT.get(cand.get("category", "other"),
                                                         CATEGORY_DEFAULT["other"])
            cand["kcal"] = kcal
            cand["protein"] = protein
            cand["sodium"] = sodium
            cand["nutrition_source"] = "同类均值估算（营养表无该新品）"

    payload["refined_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    payload["source_tools"] = sorted(set(payload.get("source_tools", []) + ["query-meal-detail"]))
    payload["candidates"] = cands
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    matched = sum(1 for c in cands if not c.get("estimated"))
    print("完成拆解：%d，当前营养覆盖率：%d/%d" % (refined, matched, len(cands)))
    print("已写入：%s" % os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
