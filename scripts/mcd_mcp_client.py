#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦当劳 MCP Streamable HTTP 客户端（仅标准库，零第三方依赖）。

对 https://mcp.mcd.cn 做 JSON-RPC 直连：
    initialize -> tools/list -> tools/call

子命令：
    ping                     校验 Token 与连通性
    tools-list               列出全部工具（可 --out 导出含入参 schema）
    call <tool> '<json>'     调用任意工具
    fetch-stores             查询门店（城市+关键词，或收藏门店）
    fetch-menu               拉取门店菜单并转换为份量引擎候选集
    fetch-nutrition          拉取餐品营养表并转换为标准 JSON

Token 读取优先级：--token > 环境变量 MCD_MCP_TOKEN > .env 文件。
Token 只用于请求头，不会写入任何输出文件。
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT = 40

# ------------------------------------------------------ 分类映射（菜单分类 -> 引擎类别）

CATEGORY_RULES = [
    ("drink", ("饮", "咖啡", "茶", "牛奶", "可乐", "雪碧", "果汁", "酷")),
    ("dessert", ("甜品", "派", "新地", "旋风", "圆筒", "冰淇淋", "蛋糕")),
    ("side", ("小食", "薯条", "薯饼", "鸡块", "鸡翅", "鸡排", "玉米", "油条", "沙拉", "蘸酱", "麦乐鸡", "拼盘")),
    ("main", ("堡", "卷", "鸡腿", "牛", "鱼", "饭", "面", "麦满分", "乐园")),
    ("soup", ("汤", "粥")),
]

# 套餐类：名称里出现这些词视为含主食+小食+饮品的组合
COMBO_HINTS = ("件套", "套餐", "组合", "全家桶", "拼盘")


class McpError(RuntimeError):
    pass


# ------------------------------------------------------ Token

def load_token(cli_token: str = "") -> str:
    if cli_token:
        return cli_token
    env = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if env:
        return env
    roots = (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.getcwd())
    for base in roots:
        env_path = os.path.join(base, ".env")
        if os.path.isfile(env_path):
            with open(env_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("MCD_MCP_TOKEN="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# ------------------------------------------------------ 协议

def rpc(method: str, params: dict, token: str, url: str) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": "Bearer " + token,
        "User-Agent": "mcd-just-enough/1.0",
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise McpError("401 Token 无效、已过期或未提供，请检查 MCD_MCP_TOKEN。")
        if exc.code == 429:
            raise McpError("429 触发限流（600 次/分钟），请降低调用频率。")
        raise McpError("HTTP %s：%s" % (exc.code, detail[:400]))
    except urllib.error.URLError as exc:
        raise McpError("网络错误：%r（若需代理请检查系统代理设置）" % (exc,))

    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("event:") or "\ndata:" in raw or raw.startswith("data:"):
        data_lines = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
        raw = "\n".join(data_lines)
    try:
        msg = json.loads(raw)
    except ValueError:
        raise McpError("响应不是合法 JSON：%s" % raw[:300])
    if "error" in msg:
        err = msg["error"]
        raise McpError("MCP 错误 %s：%s" % (err.get("code"), err.get("message")))
    return msg.get("result", {})


def initialize(token: str, url: str) -> dict:
    return rpc("initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "mcd-just-enough", "version": "1.0.0"},
    }, token, url)


def tools_list(token: str, url: str) -> list:
    return rpc("tools/list", {}, token, url).get("tools", [])


def call_tool(name: str, arguments: dict, token: str, url: str) -> dict:
    return rpc("tools/call", {"name": name, "arguments": arguments or {}}, token, url)


# ------------------------------------------------------ 响应解析

def extract_json(text):
    """麦当劳 MCP 的返回值是「说明文字 + JSON」混合体，这里把 JSON 部分抠出来。"""
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    starts = [i for i in (stripped.find('{"'), stripped.find("[{")) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    open_ch = stripped[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(stripped[start:idx + 1])
                except ValueError:
                    break
    return None


def unwrap(result: dict):
    """把 MCP 工具返回统一成 Python 对象（优先返回业务 data）。"""
    content = result.get("content") or []
    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
    joined = "\n".join(texts).strip()
    parsed = extract_json(joined)
    if parsed is None:
        return joined
    if isinstance(parsed, dict) and "data" in parsed and "success" in parsed:
        if not parsed.get("success"):
            raise McpError("接口返回失败：%s / %s" % (parsed.get("code"), parsed.get("message")))
        data = parsed.get("data")
        inner = extract_json(data) if isinstance(data, str) else data
        return inner if inner is not None else data
    return parsed


# ------------------------------------------------------ 业务解析

def parse_nutrition_text(raw: str) -> list:
    """解析 list-nutrition-foods 返回的自定义文本表。

    形如：
        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,
              fat,carbohydrate,sodium,calcium}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    rows = []
    if not isinstance(raw, str):
        return rows
    lines = raw.splitlines()
    header_cols = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and "{" in line:
            header_cols = [c.strip() for c in line[line.find("{") + 1:line.find("}")].split(",")]
            continue
        if header_cols is None or line.startswith("#") or line.startswith("-"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 9:
            continue
        # 名称里可能出现逗号，按「末尾 8 个字段固定」反推
        name = ",".join(parts[:len(parts) - 8])
        rest = parts[len(parts) - 8:]

        def num(idx, default=0.0):
            try:
                return float(rest[idx])
            except (ValueError, IndexError):
                return default

        rows.append({
            "productName": name,
            "kcal": num(2),
            "protein": num(3),
            "fat": num(4),
            "carbohydrate": num(5),
            "sodium": num(6),
            "calcium": num(7),
            "energyKj": num(1),
        })
    return rows


def guess_category(category_name: str, meal_name: str) -> str:
    text = "%s %s" % (category_name or "", meal_name or "")
    for cat, keys in CATEGORY_RULES:
        for key in keys:
            if key in text:
                return cat
    return "other"


def is_combo(name: str) -> bool:
    return any(h in (name or "") for h in COMBO_HINTS)


def menu_to_candidates(menu_obj: dict, nutrition_rows: list) -> list:
    """把 query-meals 的 {categories, meals} 结构转成份量引擎候选集。"""
    if not isinstance(menu_obj, dict):
        return []
    cat_map = {}
    for cat in menu_obj.get("categories") or []:
        for entry in cat.get("meals") or []:
            code = str(entry.get("code") or "")
            if code:
                cat_map[code] = cat.get("name") or ""

    nutrition_by_name = {r["productName"]: r for r in nutrition_rows}
    out = []
    for code, detail in (menu_obj.get("meals") or {}).items():
        if not isinstance(detail, dict):
            continue
        name = str(detail.get("name") or "").strip()
        if not name:
            continue
        try:
            price = float(detail.get("currentPrice") or detail.get("originalPrice") or 0)
        except (TypeError, ValueError):
            price = 0.0
        category = guess_category(cat_map.get(str(code), ""), name)
        if is_combo(name):
            category = "combo"
        cand = {
            "code": str(code),
            "name": name,
            "price": round(price, 2),
            "category": category,
            "tags": detail.get("tags") or [],
            "optional": category not in ("main", "combo"),
            "max_qty": 2 if category != "combo" else 1,
            "estimated": True,
        }
        hit = match_nutrition(name, nutrition_by_name)
        if hit:
            cand["kcal"] = hit["kcal"]
            cand["protein"] = hit["protein"]
            cand["sodium"] = hit["sodium"]
            cand["nutrition_source"] = "list-nutrition-foods"
            cand["estimated"] = False
        out.append(cand)
    out.sort(key=lambda c: (c["category"], c["code"]))
    return out


def normalize_name(text: str) -> str:
    """归一化菜名：统一括号、去掉空格与装饰符号，便于跨写法匹配。"""
    if not text:
        return ""
    table = {
        "（": "(", "）": ")", "【": "", "】": "", "“": "", "”": "",
        "「": "", "」": "", "＋": "+", " ": "", "\u3000": "",
    }
    out = str(text)
    for src, dst in table.items():
        out = out.replace(src, dst)
    return out.strip()


def match_nutrition(name: str, nutrition_by_name: dict):
    """菜名 -> 营养行。

    三级匹配：原名精确 -> 归一化精确 -> 归一化双向包含（取最长）。
    """
    if name in nutrition_by_name:
        return nutrition_by_name[name]
    norm_map = {}
    for product, row in nutrition_by_name.items():
        key = normalize_name(product)
        if key and key not in norm_map:
            norm_map[key] = row
    target = normalize_name(name)
    if target in norm_map:
        return norm_map[target]
    best, best_len = None, 0
    for key, row in norm_map.items():
        if key and (key in target or target in key):
            if len(key) > best_len:
                best, best_len = row, len(key)
    return best


# ------------------------------------------------------ 子命令

def cmd_fetch_stores(args, token, url):
    params = {"beType": args.be_type, "searchType": 1 if args.favorites else 2}
    if args.city:
        params["city"] = args.city
    if args.keyword:
        params["keyword"] = args.keyword
    data = unwrap(call_tool("query-nearby-stores", params, token, url))
    stores = data if isinstance(data, list) else []
    payload = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_tool": "query-nearby-stores",
        "params": {k: v for k, v in params.items()},
        "stores": [{
            "storeCode": s.get("storeCode"),
            "storeName": s.get("storeName"),
            "address": s.get("address"),
            "distance": s.get("distance"),
            "businessStatus": s.get("businessStatus"),
            "businessHours": "%s-%s" % (s.get("businessStartTime"), s.get("businessEndTime")),
        } for s in stores],
    }
    dump(payload, args.out)
    if not args.out:
        for s in payload["stores"][:20]:
            print("%s | %s | %s" % (s["storeCode"], s["storeName"], s["address"]))
    else:
        print("门店数量：%d" % len(payload["stores"]))
    return 0


def cmd_fetch_menu(args, token, url):
    nutrition_rows = []
    if not args.no_nutrition:
        nutrition_rows = parse_nutrition_text(
            unwrap(call_tool("list-nutrition-foods", {}, token, url)))
    params = {"storeCode": args.store_code, "orderType": args.order_type, "beType": args.be_type}
    if args.be_code:
        params["beCode"] = args.be_code
    menu = unwrap(call_tool("query-meals", params, token, url))
    cands = menu_to_candidates(menu, nutrition_rows)
    payload = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": "mcp",
        "store_code": args.store_code,
        "store_name": args.store_name,
        "order_type": args.order_type,
        "be_type": args.be_type,
        "source_tools": ["query-nearby-stores", "query-meals", "list-nutrition-foods"],
        "candidates": cands,
    }
    dump(payload, args.out)
    print("餐品数量：%d（营养已匹配 %d）" % (
        len(cands), sum(1 for c in cands if not c.get("estimated"))))
    return 0


def cmd_fetch_nutrition(args, token, url):
    raw = unwrap(call_tool("list-nutrition-foods", {}, token, url))
    rows = parse_nutrition_text(raw)
    payload = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": "mcp",
        "source_tool": "list-nutrition-foods",
        "count": len(rows),
        "foods": rows,
    }
    dump(payload, args.out)
    print("营养条目：%d" % len(rows))
    return 0


def dump(payload, out_path):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("已写入：%s" % os.path.abspath(out_path))
    else:
        print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="麦当劳 MCP Streamable HTTP 客户端")
    parser.add_argument("action", choices=["ping", "tools-list", "call",
                                           "fetch-stores", "fetch-menu", "fetch-nutrition"])
    parser.add_argument("tool_or_args", nargs="?", default="")
    parser.add_argument("arguments", nargs="?", default="{}")
    parser.add_argument("--token", default="")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default="")
    # fetch-stores
    parser.add_argument("--city", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--favorites", action="store_true", help="查询收藏门店")
    # fetch-menu
    parser.add_argument("--store-code", default="")
    parser.add_argument("--store-name", default="")
    parser.add_argument("--order-type", type=int, default=1, help="1-到店自提，2-外送")
    parser.add_argument("--be-type", type=int, default=1, help="1-到店取餐，2-麦乐送，5-得来速")
    parser.add_argument("--be-code", default="")
    parser.add_argument("--no-nutrition", action="store_true")
    args = parser.parse_args()

    token = load_token(args.token)
    if not token:
        print("缺少 MCP Token：使用 --token、设置环境变量 MCD_MCP_TOKEN，或写入 .env。", file=sys.stderr)
        return 2

    try:
        if args.action == "ping":
            print(json.dumps(initialize(token, args.url), ensure_ascii=False))
            return 0
        if args.action == "tools-list":
            tools = tools_list(token, args.url)
            print("工具数量：%d" % len(tools))
            for t in tools:
                print("- %s | %s" % (t.get("name"), (t.get("description") or "").split("\n")[0][:70]))
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    json.dump(tools, fh, ensure_ascii=False, indent=2)
                print("已写入：%s" % os.path.abspath(args.out))
            return 0
        if args.action == "call":
            try:
                params = json.loads(args.arguments or "{}")
            except ValueError as exc:
                print("参数不是合法 JSON：%r" % (exc,), file=sys.stderr)
                return 2
            result = unwrap(call_tool(args.tool_or_args, params, token, args.url))
            if args.out:
                dump(result, args.out)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2)
                      if isinstance(result, (dict, list)) else str(result))
            return 0
        if args.action == "fetch-stores":
            return cmd_fetch_stores(args, token, args.url)
        if args.action == "fetch-menu":
            if not args.store_code:
                print("fetch-menu 需要 --store-code。", file=sys.stderr)
                return 2
            return cmd_fetch_menu(args, token, args.url)
        if args.action == "fetch-nutrition":
            return cmd_fetch_nutrition(args, token, args.url)
    except McpError as exc:
        print("MCP 调用失败：%s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
