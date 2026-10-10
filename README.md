# 麦麦刚刚好 / mcd-just-enough

项目地址：https://github.com/zhuyifeiRuichuang/mcd-just-enough

当前版本：**v1.1.0**（[更新日志](CHANGELOG.md) · [全部版本](https://github.com/zhuyifeiRuichuang/mcd-just-enough/releases)）

点麦当劳最常见的浪费不是点贵了，而是**点多了**：单人套餐吃不完、双人点三件套剩一堆、给孩子点成人份、加班夜宵怕撑又怕饿。

麦麦刚刚好不追求「最便宜」，也不追求「热量最低」，只回答一个没人回答的问题：

> 这一顿，到底点多少才刚刚好？

基于麦当劳官方 MCP，根据人数、食量、场景、预算与历史反馈，输出**保守 / 刚好 / 丰盛**三档方案，给出份量条、饱腹评分、**预估浪费率与浪费金额**，并用 `calculate-price` 做官方核价，停在付款前由用户确认。

---

## 一、准备环境

| 项目 | 要求 |
|---|---|
| Python | 3.8 及以上，仅使用标准库，无需安装任何依赖 |
| MCP Token | 在 https://open.mcd.cn/mcp 申请 |
| MCP Client | 支持 Streamable HTTP 的客户端，如 WorkBuddy、Cursor、Cherry Studio、Trae |
| 网络 | 可访问 `https://mcp.mcd.cn` |

无 MCP Token 时可用内置样例数据跑通全流程（演示模式），但参赛与真实使用必须走真实 MCP。

---

## 二、配置文件

### 1. 配置 MCP

复制 `mcp-config.example.json`，把 Token 通过环境变量注入：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

> 配置文件只允许环境变量占位符，禁止写入真实 Token。

### 2. 准备候选菜单

由 `query-meals` 与 `list-nutrition-foods` 的结果整理成 `candidates.json`：

```json
{
  "candidates": [
    {
      "code": "9900013301",
      "name": "巨无霸",
      "category": "main",
      "price": 24.5,
      "kcal": 550,
      "protein": 31,
      "sodium": 1020,
      "max_qty": 2,
      "satiety_solid": 1.0,
      "tags": ["牛肉"],
      "optional": false
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `code` | 餐品编码，`query-meals` 返回 |
| `category` | `main` / `side` / `drink` / `dessert` |
| `price` | 单价 |
| `kcal` / `protein` / `sodium` | 来自 `list-nutrition-foods` |
| `max_qty` | 单品最多点几份 |
| `satiety_solid` | 固形物系数，主食 1.0、小食 0.55–0.85、甜品 0.5、饮品 0.2–0.35 |
| `tags` | 用于忌口过滤，如 `辣`、`碳酸` |
| `optional` | `false` 表示必须出现在方案中 |

套餐可用 `codes` 字段传入组成餐品编码列表，营养值留空时会自动按组成累加。

---

## 三、使用

### 方式一：在 WorkBuddy 等 MCP Client 中直接用 Skill

安装 `SKILL.md` 后，直接说：

> 我一个人吃，正常饭量，堂食，预算 40，别点多了。

Skill 会自动走完整流程：定位门店 → 取菜单与营养 → 读历史 → 份量规划 → 官方核价 → 输出三档建议。

### 方式二：命令行（真实 MCP，完整链路）

```bash
# 0. 把 Token 放进本地 .env（已被 .gitignore 排除，不会进 Git）
echo "MCD_MCP_TOKEN=你的Token" > .env

# 1. 校验连通性，列出 35 个工具
python scripts/mcd_mcp_client.py ping
python scripts/mcd_mcp_client.py tools-list

# 2. 定位门店（收藏为空时用城市+关键词）
python scripts/mcd_mcp_client.py fetch-stores --city 济南 --keyword 济南 --out stores.json

# 3. 取营养表与门店菜单
python scripts/mcd_mcp_client.py fetch-nutrition --out nutrition.json
python scripts/mcd_mcp_client.py fetch-menu --store-code 3350050 --out candidates.json

# 4. 拆解套餐，累加真实热量
python scripts/refine_combos.py --candidates candidates.json \
  --nutrition nutrition.json --store-code 3350050 --out candidates_refined.json

# 5. 份量规划
python scripts/plan_just_enough.py \
  --people 1 --appetite normal --scene solo --dining dine_in --budget 45 \
  --candidates candidates_refined.json --nutrition nutrition.json \
  --data-source mcp --store "麦当劳济南火车站站外广场餐厅" --out plan.json

# 6. 官方核价（只核价，不下单）
python scripts/check_price.py --plan plan.json --all-tiers \
  --store-code 3350050 --out price.json

# 7. 生成单文件 HTML 报告
python scripts/build_report.py --plan plan.json --price price.json \
  --store "麦当劳济南火车站站外广场餐厅" --out report.html

# 8. 餐后反馈
python scripts/apply_feedback.py --history history.jsonl --plan-id <plan_id> --result over
```

参数说明：

| 参数 | 取值 |
|---|---|
| `--people` | 人数 |
| `--appetite` | `light` / `normal` / `heavy` |
| `--scene` | `solo` / `pair` / `family` / `work` / `night` |
| `--dining` | `dine_in` / `takeout` / `delivery` / `drive_thru` |
| `--budget` | 预算上限，0 表示不限 |
| `--avoid` | 忌口标签，逗号分隔，如 `辣,碳酸` |
| `--data-source` | `mcp` 真实数据 / `sample` 样例数据 |

### 离线演示（无 Token）

```bash
python scripts/plan_just_enough.py \
  --people 1 --appetite normal --scene solo --dining dine_in --budget 40 \
  --candidates examples/sample_menu.json --data-source sample --out demo_plan.json

python scripts/build_report.py --plan demo_plan.json --out demo_report.html
```

### 真实取数快照

`examples/real_*.json` 是一次真实调用的完整留档，无需 Token 即可复盘：

| 文件 | 内容 |
|---|---|
| `real_stores_jinan.json` | `query-nearby-stores` 返回的 5 家济南门店 |
| `real_nutrition.json` | `list-nutrition-foods` 返回的 160 条餐品营养 |
| `real_menu_3350050.json` | `query-meals` + `query-meal-detail` 得到的 87 个在售餐品 |
| `real_plan.json` | 引擎输出的三档方案 |
| `real_price.json` | `calculate-price` 的官方核价结果 |
| `demo-report.html` | 上述数据生成的报告，可直接打开 |

实测：保守 ¥31.0 / 刚好 ¥37.5 / 丰盛 ¥45.0，官方核价与引擎按菜单价的估算**完全一致**。

---

## 四、输出说明

每档方案包含：

1. 组合清单（品名 + 份数 + 编码）
2. 份量条：`[======··|·····]`，`|` 为胃口线，`=` 为本档份量
3. 能量、蛋白质与饱腹评分
4. 预估浪费率与浪费金额
5. 官方核价结果
6. 一句话理由

HTML 报告为单文件，内联 CSS 与 JS，无任何外部依赖，可直接双击打开或截图分享。

---

## 五、目标用户

- 一个人吃麦当劳，不知道点多少才不会剩的独食党
- 两人同行，怕点多吃不完的情侣与同事
- 想控制摄入又不想饿着的人
- 带孩子吃饭，不想点成人份的家长
- 加班或夜宵场景，怕撑又怕饿的职场人

---

## 六、项目结构

```
mcd-just-enough/
├── SKILL.md                        Skill 入口与标准工作流
├── README.md                       本文档
├── CHANGELOG.md                    版本更新日志
├── MCP_INTEGRATION.md              MCP 调用说明与业务价值
├── CONTEST_DECLARATION.md          参赛声明（官方文件，不得修改）
├── mcp-config.example.json         MCP 配置示例（仅环境变量占位符）
├── workbuddy.md                    WorkBuddy 开发上下文
├── scripts/
│   ├── mcd_mcp_client.py         MCP 客户端：ping / tools-list / call / fetch-*
│   ├── refine_combos.py          套餐拆解，累加真实热量
│   ├── plan_just_enough.py       份量规划引擎
│   ├── check_price.py            官方核价（calculate-price）
│   ├── build_report.py           单文件 HTML 报告生成器
│   └── apply_feedback.py         餐后反馈写入
├── references/
│   ├── portion-model.md          份量与浪费模型
│   ├── mcp-tools.md              35 个工具清单与实测入参要点
│   └── history-format.md         历史与反馈数据格式
├── examples/
│   ├── sample_menu.json          离线演示样例菜单
│   ├── real_*.json               真实接口取数快照
│   └── demo-report.html          真实数据生成的报告
└── .env                          本地 Token（不进 Git）
```

全部脚本仅使用 Python 标准库，无需安装任何依赖。

---

## 七、合规与免责

- 不包含真实 Token、密钥、密码、账号凭证，配置文件仅使用环境变量占位符
- 不进行跨品牌或跨平台的价格与品质对比
- 营养数据仅用于份量估算，不构成医疗、营养或其他专业建议
- 餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准
- 未经用户明确确认，不会调用 `create-order`，不会代替用户支付
- 本项目由参赛者独立开发，非麦当劳官方产品
