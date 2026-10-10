#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦麦刚刚好 —— 餐后反馈写入。

用法：
    python scripts/apply_feedback.py --history history.jsonl \
        --plan-id 8f2c1a9b3d21 --result fit
        [--tier fit] [--note "两个人吃刚好"]

反馈会更新个人份量系数，下一次规划时自动生效。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

VALID = {"under": "没吃够", "fit": "刚好", "over": "有剩余"}


def main() -> int:
    parser = argparse.ArgumentParser(description="写入餐后反馈")
    parser.add_argument("--history", default="history.jsonl")
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--result", required=True, choices=sorted(VALID))
    parser.add_argument("--tier", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    record = {
        "type": "feedback",
        "plan_id": args.plan_id,
        "tier": args.tier,
        "result": args.result,
        "result_text": VALID[args.result],
        "note": args.note,
        "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    with open(args.history, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    hint = {
        "under": "已记录：下次会略微上调份量建议。",
        "fit": "已记录：当前份量系数将被强化。",
        "over": "已记录：下次会略微下调份量建议，减少浪费。",
    }[args.result]

    print("反馈已写入 {}：{}".format(args.history, json.dumps(record, ensure_ascii=False)))
    print(hint)
    print("样本文件仅保存在本地，请勿提交真实个人信息。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
