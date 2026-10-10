#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦麦刚刚好 / McJustEnough —— 份量规划引擎。

基于麦当劳官方 MCP 取到的菜单、营养、历史订单与本地反馈，
计算一顿饭真正合适的份量，输出「保守 / 刚好 / 丰盛」三档方案，
并给出份量条、饱腹评分、预估浪费率与浪费金额。

仅使用 Python 标准库，无任何第三方依赖。
用法见 SKILL.md。

设计要点：
  1. 先锁定「刚好」档：偏差惩罚远大于价格惩罚，保证优先命中胃口线。
  2. 再由「刚好」派生保守档（减一份可选项）与丰盛档（加一份小食/甜品），
     保证三档单调且互不相同。
  3. 浪费不是附加信息：超限部分按就餐方式的丢弃比例折算成浪费率与浪费金额。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import uuid

# ---------------------------------------------------------------- 常量

APPETITE_FACTOR = {"light": 0.85, "normal": 1.00, "heavy": 1.18}
SCENE_FACTOR = {
    "solo": 1.00,    # 独食：按基准
    "pair": 0.90,    # 两人：小食与饮品会共享，人均需求低于独食
    "family": 0.92,  # 带娃：按孩子实际食量，下调
    "work": 0.95,    # 加班：怕撑，略下调
    "night": 0.82,   # 夜宵：明显下调
}
DINING_FACTOR = {
    "dine_in": 1.00,
    "takeout": 0.97,     # 外带路上会凉，实际吃到略少
    "delivery": 0.95,    # 麦乐送同理
    "drive_thru": 1.00,
}
WASTE_RATIO = {
    "dine_in": 0.75,     # 堂食吃不完的部分大多直接丢弃
    "takeout": 0.40,     # 外带可带走，浪费率低
    "delivery": 0.40,
    "drive_thru": 0.55,
}
BASE_KCAL = 700.0
SATIETY_PER_KCAL = 1.28     # 饱腹单位与能量的换算系数（见 references/portion-model.md）
MAX_ITEMS = 6
MAX_KCAL = 4000.0
W_SATIETY = 45.0
W_WASTE = 25.0
W_PRICE = 1.6
PENALTY_BUDGET = 40.0
PENALTY_MISS = 15.0
PENALTY_DEVIATION_CAP = 30.0
PENALTY_FAR = 80.0
PENALTY_ESTIMATED = 8.0     # 每出现一个「估算营养」的餐品扣分，优先选真实数据
DEVIATION_CAP = 0.15        # 超过胃口线 15% 视为明显偏离
BUDGET_TOLERANCE = 1.25     # 超过预算 25% 的组合直接不考虑


# ---------------------------------------------------------------- 工具函数

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def combo_kcal(codes: list, nutrition: dict) -> float:
    total = 0.0
    for code in codes:
        row = nutrition.get(code)
        if row is None:
            return 0.0
        total += float(row.get("kcal", 0) or 0)
    return total


def item_kcal(cand: dict, nutrition: dict) -> float:
    kcal = cand.get("kcal")
    if kcal is not None:
        return float(kcal or 0.0)
    return combo_kcal(cand.get("codes") or [cand.get("code", "")], nutrition)


def item_satiety(cand: dict, nutrition: dict) -> float:
    """单份饱腹贡献。

    以能量为主（单品能量按 900 kcal 截断，避免超大单品失真），
    叠加蛋白质、固形物与少量钠带来的饱腹加成。
    """
    kcal = item_kcal(cand, nutrition)
    protein = float(cand.get("protein", 0) or 0)
    sodium = float(cand.get("sodium", 0) or 0)
    solid = float(cand.get("satiety_solid", 0.8) or 0.8)

    energy_term = min(kcal, 900.0) / 100.0
    protein_term = protein / 10.0 * 0.35
    solid_term = energy_term * solid * 0.25
    sodium_term = min(sodium, 2000.0) / 1000.0 * 0.3
    return energy_term + protein_term + solid_term + sodium_term


def sum_satiety(combo: list, nutrition: dict) -> float:
    return sum(item_satiety(c, nutrition) * q for c, q in combo)


def sum_price(combo: list) -> float:
    return sum(float(c.get("price", 0) or 0) * q for c, q in combo)


def sum_kcal(combo: list, nutrition: dict) -> float:
    return sum(item_kcal(c, nutrition) * q for c, q in combo)


def sum_protein(combo: list) -> float:
    return sum(float(c.get("protein", 0) or 0) * q for c, q in combo)


def need_kcal(need: dict) -> float:
    """胃口线（能量口径）。"""
    people = max(1, int(need["people"]))
    return (
        BASE_KCAL
        * people
        * APPETITE_FACTOR.get(need["appetite"], 1.0)
        * SCENE_FACTOR.get(need["scene"], 1.0)
        * DINING_FACTOR.get(need["dining"], 1.0)
        * float(need.get("feedback_factor", 1.0))
    )


def target_satiety(need: dict, tier_factor: float) -> float:
    """某档的饱腹目标（饱腹单位口径）。"""
    return need_kcal(need) * tier_factor * SATIETY_PER_KCAL / 100.0


def waste_estimate(combo: list, need: dict, target: float, nutrition: dict) -> tuple:
    """预估超出胃口的部分带来的浪费率与浪费金额。"""
    kcal = sum_kcal(combo, nutrition)
    need_line = need_kcal(need)
    price = sum_price(combo)
    if kcal <= need_line or price <= 0:
        return 0.0, 0.0

    excess_ratio = (kcal - need_line) / kcal
    ratio = clamp(
        excess_ratio * WASTE_RATIO.get(need["dining"], 0.6)
        * (1.0 if target <= need_line else 1.15),
        0.0,
        1.0,
    )
    return ratio, price * ratio


def deviation(satiety: float, target: float) -> tuple:
    """返回 (相对偏差, 是否超出 15% 偏离上限)。"""
    if target <= 0:
        return 0.0, False
    rel = (satiety - target) / target
    tol = 0.03
    effective = abs(rel) - tol
    if effective <= 0:
        return 0.0, False
    return effective * (1.8 if rel > 0 else 1.0), abs(rel) > DEVIATION_CAP


def provides_of(cand: dict) -> set:
    """该餐品能满足的营养/结构角色。

    套餐（combo）由 query-meal-detail 拆解为「主食 + 小食 + 饮品」，
    因此视作同时提供这三类角色，避免引擎再叠加一份主食或饮品导致过量。
    """
    explicit = cand.get("provides")
    if explicit:
        return set(explicit)
    cat = cand.get("category", "other")
    if cat == "combo":
        return {"main", "side", "drink"}
    return {cat}


def missing_goals(combo: list, need: dict) -> int:
    """应满足但未满足的软目标数量。"""
    miss = 0
    roles = set()
    for cand, _ in combo:
        roles |= provides_of(cand)
    if "main" not in roles:
        miss += 1
    if need["dining"] != "takeout" and "drink" not in roles:
        miss += 1
    return miss


# ---------------------------------------------------------------- 组合枚举

def build_pool(candidates: list) -> list:
    pool = []
    for cand in candidates:
        max_qty = int(cand.get("max_qty", 2) or 2)
        for q in range(1, max_qty + 1):
            pool.append((cand, q))
    pool.sort(key=lambda x: (x[0].get("code", ""), x[1]))
    return pool


def normalize_combo(combo: list) -> list:
    """合并同一餐品的多条记录，并统一按餐品编码排序。"""
    merged = {}
    order = []
    for cand, q in combo:
        if q <= 0:
            continue
        code = cand.get("code", "")
        if code in merged:
            merged[code]["qty"] += q
        else:
            merged[code] = {"cand": cand, "qty": q}
            order.append(code)
    return [(merged[code]["cand"], merged[code]["qty"]) for code in order]


def combo_key(combo: list) -> tuple:
    return tuple(sorted((c.get("code", ""), q) for c, q in combo))


def within_limits(combo: list, max_items: int, max_kcal: float,
                  nutrition: dict) -> bool:
    if not combo:
        return False
    for cand, q in combo:
        if q > int(cand.get("max_qty", 2) or 2):
            return False
    if sum(q for _, q in combo) > max_items:
        return False
    return sum_kcal(combo, nutrition) <= max_kcal


def greedy_seed(pool: list, target: float, nutrition: dict, max_items: int,
                max_kcal: float) -> list:
    """贪心构造一个贴近胃口线的起点，供后续变异使用。"""
    ordered = sorted(pool, key=lambda x: x[0].get("code", ""))
    seed = []
    satiety = 0.0
    for cand, _ in ordered:
        best_qty = None
        for q in range(1, int(cand.get("max_qty", 2) or 2) + 1):
            trial = normalize_combo(seed + [(cand, q)])
            if not within_limits(trial, max_items, max_kcal, nutrition):
                continue
            value = sum_satiety(trial, nutrition)
            if best_qty is None or abs(value - target) < abs(best_qty[0] - target):
                best_qty = (value, q, trial)
        if best_qty is None:
            continue
        value, q, trial = best_qty
        if satiety < target * 0.98 or value < target:
            seed.append((cand, q))
            satiety = value
    return normalize_combo(seed) or normalize_combo([ordered[0]])


def build_combos(pool: list, avoid_tags: set, max_items: int, max_kcal: float,
                 target: float, nutrition: dict, budget: float) -> list:
    """构造候选组合集合。

    采用「全量单品与双品 + 贪心种子的一步/两步变异」：
    既保证覆盖最优小组合，又能在多人场景下往上够到胃口线，
    且组合数量恒定可控（数千级），无需截断。
    """
    valid = [c for c in pool if not (set(c[0].get("tags") or []) & avoid_tags)]
    results = []
    seen = set()

    def add(combo: list):
        if not combo:
            return
        combo = normalize_combo(combo)
        if not within_limits(combo, max_items, max_kcal, nutrition):
            return
        if budget > 0 and sum_price(combo) > budget * BUDGET_TOLERANCE:
            return
        key = combo_key(combo)
        if key in seen:
            return
        seen.add(key)
        results.append(combo)

    for entry in valid:
        add([entry])

    n = len(valid)
    for i in range(n):
        for j in range(i + 1, n):
            add([valid[i], valid[j]])

    seed = greedy_seed(valid, target, nutrition, max_items, max_kcal)
    add(seed)

    frontier = [seed]
    for _ in range(2):
        nxt = []
        for combo in frontier:
            codes = {c.get("code", "") for c, _ in combo}
            for cand, _ in valid:
                for q in range(1, int(cand.get("max_qty", 2) or 2) + 1):
                    if cand.get("code", "") in codes and q == 1:
                        continue
                    trial = normalize_combo(combo + [(cand, q)])
                    add(trial)
                    nxt.append(trial)
        frontier = nxt[:80]

    return results


# ---------------------------------------------------------------- 评分

def metrics(combo: list, need: dict, nutrition: dict) -> dict:
    return {
        "combo": combo,
        "satiety": sum_satiety(combo, nutrition),
        "kcal": sum_kcal(combo, nutrition),
        "price": sum_price(combo),
        "protein": sum_protein(combo),
        "missing": missing_goals(combo, need),
    }


def tier_score(m: dict, target: float, budget: float) -> tuple:
    """返回 (分数, 相对偏差)。"""
    rel_dev, over_cap = deviation(m["satiety"], target)
    score = 100.0
    score -= W_SATIETY * rel_dev
    if rel_dev > 0.20:
        score -= PENALTY_FAR * (rel_dev - 0.20)
    if over_cap:
        score -= PENALTY_DEVIATION_CAP
    score -= W_WASTE * m.get("waste_ratio", 0.0)
    score -= W_PRICE * (m["price"] / 10.0)
    if budget > 0 and m["price"] > budget:
        excess = (m["price"] - budget) / budget
        score -= PENALTY_BUDGET * (0.3 + excess)
    score -= PENALTY_MISS * m["missing"]
    # 营养表未覆盖的新品只能按同类均值估算，可信度低于真实数据，逐项扣分
    est = sum(1 for c, _ in m["combo"] if c.get("estimated"))
    score -= PENALTY_ESTIMATED * est
    return score, rel_dev


def attach_waste(m: dict, need: dict, target: float, nutrition: dict) -> dict:
    ratio, cost = waste_estimate(m["combo"], need, target, nutrition)
    m["waste_ratio"] = ratio
    m["waste_cost"] = cost
    return m


def derive_variants(base: dict, pool_meta: list, need: dict, nutrition: dict,
                    gap: float) -> tuple:
    """由「刚好」档派生保守档与丰盛档。

    保守：去掉一份可选小食/甜品/饮品（优先去掉饱腹贡献最小的）。
    丰盛：补一件最贴合缺口的小食或甜品；没有合适的小食/甜品才考虑主食，
          最后才考虑饮品，且绝不靠把已有饮品加量来凑。
    """
    base_combo = list(base["combo"])
    base_codes = {c.get("code", "") for c, _ in base_combo}
    base_names = {c.get("name", "") for c, _ in base_combo}

    conservative = None
    optional = [(i, c, q) for i, (c, q) in enumerate(base_combo)
                if c.get("optional") is not False]
    if optional:
        idx, cand, qty = min(
            optional, key=lambda t: (item_satiety(t[1], nutrition),
                                     -float(t[1].get("price", 0) or 0)))
        trial = []
        for i, (c, q) in enumerate(base_combo):
            if i == idx:
                if q > 1:
                    trial.append((c, q - 1))
                continue
            trial.append((c, q))
        if trial:
            conservative = trial

    generous = None
    extras = [c for c in pool_meta
              if c.get("code", "") not in base_codes
              and c.get("name", "") not in base_names]
    for cats in (("side", "dessert"), ("main",), ("drink",)):
        pool = [c for c in extras if c.get("category") in cats]
        if not pool:
            continue
        best = min(
            pool,
            key=lambda c: (abs(item_satiety(c, nutrition) - gap),
                           float(c.get("price", 0) or 0),
                           1 if c.get("estimated") else 0),
        )
        generous = base_combo + [(best, 1)]
        break

    return conservative, generous


def eval_combo(combo: list, need: dict, nutrition: dict, target: float,
               budget: float) -> dict:
    m = attach_waste(metrics(combo, need, nutrition), need, target, nutrition)
    score, rel_dev = tier_score(m, target, budget)
    m["score"] = score
    m["rel_dev"] = rel_dev
    return m


def best_in_band(base_combo: list, all_combos: list, base_satiety: float,
                 need: dict, nutrition: dict, budget: float, target: float,
                 side: str) -> dict:
    """在「刚好」档的下方或上方寻找该档最优组合。

    side='below'：严格低于基准饱腹值，且不能是基准的子集缺失主项。
    side='above'：严格高于基准饱腹值。
    """
    best = None
    for combo in all_combos:
        satiety = sum_satiety(combo, nutrition)
        if side == "below" and not (satiety < base_satiety - 1e-9):
            continue
        if side == "above" and not (satiety > base_satiety + 1e-9):
            continue
        if sum_kcal(combo, nutrition) > MAX_KCAL:
            continue
        m = eval_combo(combo, need, nutrition, target, budget)
        if best is None or m["score"] > best["score"]:
            best = m
    return best


def max_items_for(need: dict) -> int:
    """件数上限：随人数放宽，避免两人场景反而选不出组合。"""
    return min(12, 4 + 3 * max(1, int(need["people"])))


# ---------------------------------------------------------------- 反馈系数

def load_feedback_factor(history_path: str) -> tuple:
    """从本地反馈历史推算个人份量系数。返回 (factor, samples)。"""
    if not history_path or not os.path.exists(history_path):
        return 1.0, 0

    factor = 1.0
    samples = 0
    try:
        with open(history_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") != "feedback":
                    continue
                result = row.get("result")
                if result not in ("under", "over"):
                    continue
                step = 0.06 if result == "under" else -0.06
                factor = clamp(factor * (1.0 + step), 0.75, 1.35)
                samples += 1
    except OSError:
        return 1.0, 0
    return round(factor, 3), samples


# ---------------------------------------------------------------- 输出

def pack_tier(tier_id: str, label: str, m: dict, need: dict, score: float,
              target: float) -> dict:
    combo = m["combo"]
    # 同一餐品可能被拆成多条（例如 ×1 与 ×2 同时入选），展示前先合并
    merged = {}
    order = []
    for cand, q in combo:
        code = cand.get("code", "")
        if code in merged:
            merged[code]["qty"] += q
        else:
            merged[code] = {"cand": cand, "qty": q}
            order.append(code)

    items = []
    for code in order:
        cand = merged[code]["cand"]
        q = merged[code]["qty"]
        unit = float(cand.get("price", 0) or 0)
        items.append({
            "code": code,
            "codes": cand.get("codes") or [code],
            "name": cand.get("name", ""),
            "category": cand.get("category", "other"),
            "qty": q,
            "price": round(unit, 2),
            "subtotal": round(unit * q, 2),
        })

    need_line = need_kcal(need)
    kcal = m["kcal"]
    if kcal < need_line * 0.92:
        reason = "低于胃口线，适合真的不饿或想控制摄入。"
    elif kcal > need_line * 1.12:
        reason = "高于胃口线，适合很饿或两人分享，注意可能吃不完。"
    else:
        reason = "贴近胃口线，是最接近「刚刚好」的一档。"

    return {
        "tier": tier_id,
        "label": label,
        "items": items,
        "price": round(m["price"], 2),
        "kcal": round(kcal, 1),
        "protein": round(m["protein"], 1),
        "satiety": round(m["satiety"], 2),
        "target": round(target, 2),
        "need": round(need_line, 1),
        "waste_ratio": round(m.get("waste_ratio", 0.0), 4),
        "waste_cost": round(m.get("waste_cost", 0.0), 2),
        "score": round(score, 2),
        "reason": reason,
        "official_price": None,
    }


def empty_tier(tier_id: str, label: str, reason: str) -> dict:
    return {
        "tier": tier_id, "label": label, "items": [], "price": 0.0,
        "kcal": 0.0, "protein": 0.0, "satiety": 0.0, "target": 0.0,
        "need": 0.0, "waste_ratio": 0.0, "waste_cost": 0.0, "score": 0.0,
        "reason": reason, "official_price": None,
    }


def portion_bar(kcal: float, need: float, width: int = 16) -> str:
    need = float(need or 0)
    kcal = float(kcal or 0)
    if need <= 0:
        need = 1.0
    scale = max(need * 1.6, kcal)
    pos = int(round(clamp(kcal / scale, 0.0, 1.0) * width))
    mark = int(round(clamp(need / scale, 0.0, 1.0) * width))
    chars = []
    for i in range(width):
        if i == mark:
            chars.append("|")
        elif i < pos:
            chars.append("=")
        else:
            chars.append("·")
    return "[" + "".join(chars) + "]"


def markdown_summary(plan: dict) -> str:
    need = plan["need"]
    lines = ["## 麦麦刚刚好 · 份量建议", ""]
    lines.append("- 场景：{} 人 · {} · {} · {}".format(
        need["people"], need["appetite"], need["scene"], need["dining"]))
    if need.get("budget"):
        lines.append("- 预算：{} 元".format(need["budget"]))
    lines.append("- 胃口线：约 {} kcal（个人份量系数 {}，历史反馈 {} 条）".format(
        plan.get("need_kcal"), plan.get("feedback_factor"), plan.get("feedback_samples")))
    lines.append("- 数据来源：{}".format(plan.get("data_source")))
    lines.append("")
    for tier in plan["tiers"]:
        if not tier["items"]:
            continue
        combo = " + ".join("{}×{}".format(i["name"], i["qty"]) for i in tier["items"])
        lines.append("### {}档：{}".format(tier["label"], combo))
        lines.append("")
        lines.append("- 份量条：`{}`".format(
            portion_bar(tier["kcal"], plan.get("need_kcal", 0))))
        lines.append("- {} kcal · 蛋白 {} g · 合计 ¥{}".format(
            tier["kcal"], tier["protein"], tier["price"]))
        lines.append("- 预估浪费率 {:.0%}（约 ¥{}）".format(
            tier["waste_ratio"], tier["waste_cost"]))
        lines.append("- {}".format(tier["reason"]))
        lines.append("")
    lines.append("> 以上为建议与官方核价结果，尚未下单。确认后我再调用 create-order。")
    lines.append("> 非麦当劳官方产品，输出仅供参考，餐品信息与价格以官方实时结果为准。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 主流程

def main() -> int:
    parser = argparse.ArgumentParser(description="麦麦刚刚好份量规划引擎")
    parser.add_argument("--people", type=int, default=1)
    parser.add_argument("--appetite", default="normal",
                        choices=["light", "normal", "heavy"])
    parser.add_argument("--scene", default="solo",
                        choices=["solo", "pair", "family", "work", "night"])
    parser.add_argument("--dining", default="dine_in",
                        choices=["dine_in", "takeout", "delivery", "drive_thru"])
    parser.add_argument("--budget", type=float, default=0.0)
    parser.add_argument("--avoid", default="", help="忌口标签，逗号分隔，例如 辣,碳酸")
    parser.add_argument("--candidates", required=True,
                        help="候选菜单 JSON（可由 query-meals 生成）")
    parser.add_argument("--nutrition", default="",
                        help="营养表 JSON（可由 list-nutrition-foods 生成）")
    parser.add_argument("--history", default="history.jsonl")
    parser.add_argument("--data-source", default="mcp", choices=["mcp", "sample"])
    parser.add_argument("--store", default="")
    parser.add_argument("--out", default="plan.json")
    args = parser.parse_args()

    with open(args.candidates, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    candidates = payload.get("candidates") if isinstance(payload, dict) else payload
    if not candidates:
        print("候选菜单为空：请检查 --candidates 文件。", file=sys.stderr)
        return 2

    nutrition = {}
    if args.nutrition and os.path.exists(args.nutrition):
        with open(args.nutrition, "r", encoding="utf-8") as fh:
            nut_payload = json.load(fh)
        rows = nut_payload.get("foods") if isinstance(nut_payload, dict) else nut_payload
        for row in rows or []:
            key = row.get("code") or row.get("productName")
            if key:
                nutrition[key] = row

    factor, samples = load_feedback_factor(args.history)
    need = {
        "people": args.people,
        "appetite": args.appetite,
        "scene": args.scene,
        "dining": args.dining,
        "budget": args.budget,
        "avoid": [t.strip() for t in args.avoid.split(",") if t.strip()],
        "feedback_factor": factor,
    }

    budget = float(args.budget or 0)
    max_items = max_items_for(need)
    pool = build_pool(candidates)
    base_target = target_satiety(need, 1.00)
    combos = build_combos(pool, set(need["avoid"]), max_items, MAX_KCAL,
                          base_target, nutrition, budget)

    if not combos:
        print("没有满足忌口、预算与件数上限的组合。", file=sys.stderr)
        return 3

    all_metrics = [metrics(combo, need, nutrition) for combo in combos]
    for m in all_metrics:
        m.update(eval_combo(m["combo"], need, nutrition, base_target, budget))
    all_metrics.sort(key=lambda x: (-x["score"], x["price"], x["kcal"]))
    base = all_metrics[0]
    base_satiety = base["satiety"]

    # 丰盛档的缺口：目标饱腹比「刚好」档多出的部分，用它去挑最合适的加菜
    gap = max(0.0, target_satiety(need, 1.22) - base_satiety)
    conservative_combo, generous_combo = derive_variants(
        base, candidates, need, nutrition, gap
    )

    tiers = []
    variants = [
        ("conservative", "保守", 0.80, "below", conservative_combo),
        ("fit", "刚好", 1.00, None, base["combo"]),
        ("generous", "丰盛", 1.22, "above", generous_combo),
    ]
    for tier_id, label, factor_v, side, fallback in variants:
        target = target_satiety(need, factor_v)
        if tier_id == "fit":
            chosen = base
        else:
            band = best_in_band(base["combo"], combos, base_satiety, need,
                                nutrition, budget, target, side)
            if band is not None:
                chosen = band
            elif fallback:
                chosen = eval_combo(fallback, need, nutrition, target, budget)
            else:
                tiers.append(empty_tier(
                    tier_id, label,
                    "当前候选下无法派生该档，请放宽忌口或预算。"))
                continue
        tiers.append(pack_tier(tier_id, label, chosen, need,
                               chosen["score"], target))

    plan = {
        "plan_id": uuid.uuid4().hex[:12],
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "skill": "mcd-just-enough",
        "version": "1.0.0",
        "data_source": args.data_source,
        "store": args.store,
        "need": need,
        "need_kcal": round(need_kcal(need), 1),
        "feedback_factor": factor,
        "feedback_samples": samples,
        "tiers": tiers,
        "disclaimer": (
            "非麦当劳官方产品，输出仅供参考，不构成医疗、营养或其他专业建议；"
            "餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准。"
        ),
    }
    plan["markdown"] = markdown_summary(plan)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)

    print(markdown_summary(plan))
    print("")
    print("方案 JSON 已写入：{}".format(args.out), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
