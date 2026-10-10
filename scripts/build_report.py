#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦麦刚刚好 —— 单文件 HTML 报告生成器。

读取 plan_just_enough.py 产出的 plan.json，
输出一个内联 CSS/JS、无任何外部依赖的单文件 HTML 报告。

用法：
    python scripts/build_report.py --plan plan.json --store "示例门店" --out report.html
"""

from __future__ import annotations

import argparse
import html
import json
import os

BAR_WIDTH = 22


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def make_bar(kcal: float, need: float, width: int = BAR_WIDTH) -> str:
    need = float(need or 0)
    kcal = float(kcal or 0)
    if need <= 0:
        need = 1.0
    scale = max(need * 1.6, kcal)
    pos = int(round(min(max(kcal / scale, 0.0), 1.0) * width))
    mark = int(round(min(max(need / scale, 0.0), 1.0) * width))
    chars = []
    for i in range(width):
        if i == mark:
            chars.append("|")
        elif i < pos:
            chars.append("=")
        else:
            chars.append("·")
    return "[" + "".join(chars) + "]"


def tier_card(tier: dict, plan: dict) -> str:
    if not tier.get("items"):
        return """
    <section class="card empty">
      <h3>{label}档</h3>
      <p class="muted">{reason}</p>
    </section>""".format(label=esc(tier.get("label", "")), reason=esc(tier.get("reason", "")))

    rows = []
    for item in tier["items"]:
        rows.append(
            "      <tr><td>{}</td><td class=\"cat\">{}</td><td class=\"num\">×{}</td>"
            "<td class=\"num\">¥{}</td></tr>".format(
                esc(item.get("name", "")),
                esc(item.get("category", "")),
                esc(item.get("qty", 1)),
                esc(item.get("subtotal", 0)),
            )
        )
    items_html = "\n".join(rows)

    official = tier.get("official_price")
    if official:
        price_line = "官方核价 ¥{}（优惠 ¥{}，应付 ¥{}）".format(
            esc(official.get("total", "-")),
            esc(official.get("discount", "-")),
            esc(official.get("payable", "-")),
        )
    else:
        price_line = "菜单合计 ¥{}（未含券，待 calculate-price 核价）".format(
            esc(tier.get("price", 0))
        )

    plan_id = plan.get("plan_id", "")
    tier_id = tier.get("tier", "")

    return """
    <section class="card">
      <div class="card-head">
        <h3>{label}档</h3>
        <span class="pill">{kcal} kcal</span>
      </div>
      <pre class="bar">{bar}</pre>
      <p class="bar-note">| 为胃口线，= 为本档份量</p>
      <table class="items">
        <thead><tr><th>餐品</th><th>类别</th><th>份数</th><th>小计</th></tr></thead>
        <tbody>
{items}
        </tbody>
      </table>
      <ul class="metrics">
        <li><span>蛋白质</span><b>{protein} g</b></li>
        <li><span>合计</span><b>¥{price}</b></li>
        <li><span>预估浪费</span><b class="warn">{waste_pct} · ¥{waste_cost}</b></li>
        <li><span>匹配度</span><b>{score}</b></li>
      </ul>
      <p class="price-line">{price_line}</p>
      <p class="reason">{reason}</p>
      <div class="feedback">
        <span class="fb-label">吃完回一句：</span>
        <button type="button" onclick="pick('{plan_id}','{tier_id}','under',this)">没吃够</button>
        <button type="button" onclick="pick('{plan_id}','{tier_id}','fit',this)">刚好</button>
        <button type="button" onclick="pick('{plan_id}','{tier_id}','over',this)">有剩余</button>
      </div>
    </section>""".format(
        label=esc(tier.get("label", "")),
        kcal=esc(tier.get("kcal", 0)),
        bar=esc(make_bar(tier.get("kcal", 0), plan.get("need_kcal", 0))),
        items=items_html,
        protein=esc(tier.get("protein", 0)),
        price=esc(tier.get("price", 0)),
        waste_pct="{:.0%}".format(float(tier.get("waste_ratio", 0) or 0)),
        waste_cost=esc(tier.get("waste_cost", 0)),
        score=esc(tier.get("score", 0)),
        price_line=esc(price_line),
        reason=esc(tier.get("reason", "")),
        plan_id=esc(plan_id),
        tier_id=esc(tier_id),
    )


def build_html(plan: dict, store: str) -> str:
    need = plan.get("need", {})
    tiers_html = "\n".join(tier_card(t, plan) for t in plan.get("tiers", []))

    source_text = "麦当劳官方 MCP 实时数据" if plan.get("data_source") == "mcp" \
        else "内置样例数据（离线演示，非实时）"

    first_use = ""
    if not plan.get("feedback_samples"):
        first_use = "<p class='muted'>首次使用，按通用基准估算；餐后回一句即可开始校准。</p>"

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦麦刚刚好 · 份量报告</title>
<style>
  :root {{
    --bg: #f7f7f8;
    --card: #ffffff;
    --text: #1f2328;
    --muted: #6b7280;
    --line: #e5e7eb;
    --red: #da291c;
    --gold: #ffc72c;
    --warn: #b45309;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px 16px 56px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Microsoft YaHei", "Hiragino Sans GB", sans-serif;
    line-height: 1.6;
  }}
  .wrap {{ max-width: 1040px; margin: 0 auto; }}
  header.top {{
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 4px solid var(--red);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 20px;
  }}
  h1 {{ margin: 0 0 6px; font-size: 26px; letter-spacing: .5px; }}
  .sub {{ color: var(--muted); font-size: 14px; margin: 0 0 16px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{
    background: #fdf2f2; border: 1px solid #f6d5d2; color: #7f1d1d;
    border-radius: 999px; padding: 4px 12px; font-size: 13px;
  }}
  .chip.gold {{ background: #fffbeb; border-color: #fde68a; color: #92400e; }}
  .summary {{
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 20px 28px; margin-bottom: 20px;
  }}
  .summary h2 {{ margin: 0 0 12px; font-size: 18px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }}
  .grid div {{ background: #fafafa; border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
  .grid span {{ display: block; color: var(--muted); font-size: 12px; }}
  .grid b {{ font-size: 18px; }}
  .tiers {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 18px; }}
  .card {{
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 20px 22px;
  }}
  .card.empty {{ opacity: .75; }}
  .card-head {{ display: flex; align-items: center; justify-content: space-between; }}
  .card h3 {{ margin: 0; font-size: 19px; }}
  .pill {{
    background: var(--gold); color: #3b2f00; border-radius: 999px;
    padding: 3px 12px; font-size: 12px; font-weight: 600;
  }}
  .bar {{
    margin: 14px 0 4px; padding: 10px 12px; background: #0f172a; color: #e5e7eb;
    border-radius: 8px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 15px; overflow-x: auto; letter-spacing: 1px;
  }}
  .bar-note {{ margin: 0 0 14px; color: var(--muted); font-size: 12px; }}
  table.items {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  table.items th {{ text-align: left; color: var(--muted); font-weight: 500; font-size: 12px;
    border-bottom: 1px solid var(--line); padding: 6px 0; }}
  table.items td {{ border-bottom: 1px solid #f3f4f6; padding: 7px 0; }}
  .cat {{ color: var(--muted); font-size: 12px; }}
  .num {{ text-align: right; }}
  ul.metrics {{ list-style: none; margin: 14px 0 0; padding: 0;
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 13px; }}
  ul.metrics li {{ background: #fafafa; border: 1px solid var(--line);
    border-radius: 8px; padding: 8px 10px; display: flex; justify-content: space-between; }}
  ul.metrics span {{ color: var(--muted); }}
  .warn {{ color: var(--warn); }}
  .price-line {{ margin: 14px 0 0; font-size: 13px; color: #374151; }}
  .reason {{ margin: 8px 0 0; font-size: 13px; color: #374151; }}
  .feedback {{ margin-top: 16px; padding-top: 14px; border-top: 1px dashed var(--line);
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .fb-label {{ font-size: 12px; color: var(--muted); }}
  button {{
    border: 1px solid var(--line); background: #fff; color: var(--text);
    border-radius: 8px; padding: 6px 14px; font-size: 13px; cursor: pointer;
  }}
  button:hover {{ border-color: var(--red); color: var(--red); }}
  button.active {{ background: var(--red); border-color: var(--red); color: #fff; }}
  .fb-out {{
    margin-top: 18px; background: #0f172a; color: #e5e7eb; border-radius: 10px;
    padding: 14px 16px; font-size: 12.5px; display: none;
  }}
  .fb-out.show {{ display: block; }}
  .fb-out code {{ color: #fde68a; word-break: break-all; }}
  .fb-out button {{ margin-top: 10px; }}
  .muted {{ color: var(--muted); font-size: 13px; }}
  footer {{ margin-top: 26px; color: var(--muted); font-size: 12.5px;
    background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px; }}
  footer p {{ margin: 0 0 6px; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>麦麦刚刚好 · 份量报告</h1>
    <p class="sub">不追求最便宜，也不追求热量最低，只回答：这一顿点多少才刚刚好。</p>
    <div class="chips">
      <span class="chip">{people} 人</span>
      <span class="chip">{scene}</span>
      <span class="chip">{dining}</span>
      <span class="chip gold">胃口线 {need_kcal} kcal</span>
      <span class="chip">{source}</span>
    </div>
  </header>

  <section class="summary">
    <h2>这一顿的判断依据</h2>
    <div class="grid">
      <div><span>食量档位</span><b>{appetite}</b></div>
      <div><span>场景系数</span><b>{scene}</b></div>
      <div><span>就餐方式</span><b>{dining}</b></div>
      <div><span>预算上限</span><b>{budget}</b></div>
      <div><span>个人份量系数</span><b>{factor}</b></div>
      <div><span>历史反馈样本</span><b>{samples}</b></div>
    </div>
    {first_use}
  </section>

  <section class="tiers">
{tiers}
  </section>

  <div class="fb-out" id="fbOut">
    <div>已记录，把这段 JSON 追加到本地 <code>history.jsonl</code>，
或执行 <code>python scripts/apply_feedback.py --history history.jsonl --plan-id &lt;id&gt; --result &lt;under|fit|over&gt;</code>：</div>
    <code id="fbJson"></code>
    <button type="button" onclick="copyFb()">复制反馈 JSON</button>
  </div>

  <footer>
    <p>{disclaimer}</p>
    <p>数据来源：{source}。{store}</p>
    <p>以上为建议与官方核价结果，尚未下单；确认下单需由用户明确授权后再调用 create-order。</p>
    <p>生成时间：{created} · 方案 ID：{plan_id}</p>
  </footer>
</div>

<script>
  var current = null;
  function pick(planId, tierId, result, btn) {{
    var box = document.getElementById('fbOut');
    var out = document.getElementById('fbJson');
    var siblings = btn.parentNode.querySelectorAll('button');
    for (var i = 0; i < siblings.length; i++) {{ siblings[i].classList.remove('active'); }}
    btn.classList.add('active');
    current = {{
      type: 'feedback',
      plan_id: planId,
      tier: tierId,
      result: result,
      ts: new Date().toISOString()
    }};
    out.textContent = JSON.stringify(current);
    box.classList.add('show');
  }}
  function copyFb() {{
    if (!current) {{ return; }}
    var text = JSON.stringify(current);
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text);
    }} else {{
      var ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }}
    var btn = document.querySelector('#fbOut button');
    var old = btn.textContent;
    btn.textContent = '已复制';
    setTimeout(function () {{ btn.textContent = old; }}, 1500);
  }}
</script>
</body>
</html>
""".format(
        people=esc(need.get("people", 1)),
        scene=esc(need.get("scene", "")),
        dining=esc(need.get("dining", "")),
        need_kcal=esc(plan.get("need_kcal", 0)),
        source=esc(source_text),
        appetite=esc(need.get("appetite", "")),
        budget=esc("{:.0f} 元".format(float(need.get("budget", 0) or 0))
                   if need.get("budget") else "不限"),
        factor=esc(plan.get("feedback_factor", 1.0)),
        samples=esc(plan.get("feedback_samples", 0)),
        first_use=first_use,
        tiers=tiers_html,
        disclaimer=esc(plan.get("disclaimer", "")),
        store=esc(("门店：" + store) if store else ""),
        created=esc(plan.get("created_at", "")),
        plan_id=esc(plan.get("plan_id", "")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成麦麦刚刚好单文件 HTML 报告")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--store", default="")
    parser.add_argument("--out", default="report.html")
    args = parser.parse_args()

    with open(args.plan, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    html_text = build_html(plan, args.store)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html_text)

    print("报告已生成：{}".format(os.path.abspath(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
