# 麦当劳 MCP 工具清单（tools/list 真实返回）

接入地址 `https://mcp.mcd.cn`，Streamable HTTP，共 **35** 个工具。

| # | Tool | 说明 | 本项目 |
|---|---|---|---|
| 1 | `auto-bind-coupons` | 自动领取麦麦省所有当前可用的麦当劳优惠券。无需指定具体的优惠券和couponId，系统会自动领取用户可领的所有券。当用户说"帮我领券"、"自 | 预留 |
| 2 | `available-coupons` | 查询用户当前可领取的麦麦省的优惠券列表。返回券名称、图片、状态和促销标签。当用户询问有什么优惠、可以领什么券时使用此工具。 | 预留 |
| 3 | `calculate-price` | Description: 计算商品的价格（含优惠），支持到店自提(orderType=1)和外送(orderType=2)两种场景 | 已用 |
| 4 | `campaign-calendar` | 查询麦当劳中国当月的营销活动日历，返回进行中、往期和未来日期的活动。适用于查看用户进行中和即将到来的可参与活动，还可查询用户对活动的订阅状态 | 预留 |
| 5 | `cancel-order` | Description: 取消订单，非商城订单 | 未使用 |
| 6 | `create-order` | Description: 创建麦当劳订单，支持到店(orderType=1)和外送(orderType=2)两种场景下单, 必须先确定订单类 | 已用 |
| 7 | `delivery-create-address` | Description: 创建用户配送地址 | 未使用 |
| 8 | `delivery-query-addresses` | Description: 外送场景下，查询用户配送地址列表 | 已用 |
| 9 | `delivery-query-stores` | Description: 外送场景下，用户选择完地址后，需要根据地址ID，查询用户当前地址可配送的门店 | 已用 |
| 10 | `draw-lottery` | Description: 使用后台配置的抽奖消耗规则参加一次当前积分抽奖并返回结果，服务端原子完成次数或积分扣减与抽奖。 | 未使用 |
| 11 | `list-nutrition-foods` | 获取麦当劳常见餐品的营养成分数据，包括能量、蛋白质、脂肪、碳水化合物、钠、钙等信息，当用户咨询麦当劳餐品的热量、营养，帮助用户搭配指定热量套 | 已用 |
| 12 | `mall-create-order` | 创建积分兑换订单，仅支持shopId=2（从 mall-product-detail 获取） - 当用户询问"用积分兑换这个商品"、"兑换这 | 未使用 |
| 13 | `mall-order-detail` | Description: 查询麦麦商城订单详情 | 未使用 |
| 14 | `mall-order-list` | Description: 查询麦麦商城订单列表 | 未使用 |
| 15 | `mall-points-products` | 查询可兑换餐品券列表 - 当用户询问"有哪些积分兑换商品"、"积分可以兑换什么"、"查看积分商城"时使用 | 未使用 |
| 16 | `mall-product-detail` | 查询积分兑换商品详情 - 当用户询问"这个商品详情是什么"、"查看商品详细信息"、用户点击商品查看详情时使用 | 未使用 |
| 17 | `now-time-info` | 获取当前时间信息 - 返回当前服务器的完整时间信息，包括： | 已用 |
| 18 | `order-list` | Description: 查询麦当劳历史订单，非商城订单，商城订单需要使用mall-order-list | 已用 |
| 19 | `party-order-create` | Description: 创建生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动, 仅支持shopId=5（从 mall-pr | 未使用 |
| 20 | `query-lottery-info` | Description: 查看当前积分抽奖活动信息，包括活动基本信息、抽奖消耗规则、单次所需积分、剩余可抽次数、当前可用积分与公开奖品列表， | 未使用 |
| 21 | `query-meal-assistance` | Description: 仅支持企业团餐场景(beType=6)在calculate-price前需要获取当前门店可用的助餐服务 | 未使用 |
| 22 | `query-meal-detail` | Description: 餐品详情, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 | 已用 |
| 23 | `query-meals` | Description: 餐品列表, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 | 已用 |
| 24 | `query-my-account` | 查询用户积分账户详情 - 当用户询问"我有多少积分"、"查下我的积分"、"积分余额"、"查询过期积分"时使用 | 未使用 |
| 25 | `query-my-coupons` | 获取用户卡包中的优惠券资产信息，用于“我有什么券 / 券详情查看”等展示与管理场景。 注意：该接口返回的是用户拥有的券，不进行门店、渠道、配 | 预留 |
| 26 | `query-my-prizes` | Description: 查询当前登录会员通过积分抽奖获得的本期及历史奖品（可用/已使用/已过期/已领取/已失效）。 | 未使用 |
| 27 | `query-nearby-stores` | Description: 到店场景下，查询用户可点餐门店，需要用户明确是到店自取还是车道取餐 | 已用 |
| 28 | `query-order` | Description: 查询订单详细信息 | 未使用 |
| 29 | `query-party-city` | Description: 活动派对商品配置场次城市列表, 必须先确定spuId(从 mall-points-products 获取）或查询商 | 未使用 |
| 30 | `query-party-store` | Description: 查询指定城市下支持主题派对的门店列表。当用户选择了城市后，需要查看该城市有哪些门店可举办生日类派对/主题类派对/麦 | 未使用 |
| 31 | `query-party-store-date` | Description: 查询指定门店支持生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动的可预约日期列表。当用户选择了门店 | 未使用 |
| 32 | `query-party-store-session` | Description: 查询指定门店、指定日期下的生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动场次列表。当用户选择了日 | 未使用 |
| 33 | `query-promotions` | Description: 查询当前门店企业团餐场景下可用的促销规则（满减/满折），仅返回当前时间有效且适用在售餐品的规则原始数据 | 预留 |

## 入参要点（实测）

| 规则 | 说明 |
|---|---|
| `orderType` | 1-到店（含到店自取 + 得来速），2-外送（含麦乐送 + 企业团餐） |
| `beType` | 1-到店取餐，2-麦乐送到家，5-得来速（DT），6-企业团餐 |
| `beCode` | 与 `storeCode` 配对使用，**到店场景不要传**（传了会报错），外送场景取自 `delivery-query-*` |
| 门店搜索 | `query-nearby-stores` 的 `searchType=1` 查收藏餐厅；收藏为空时必须改 `searchType=2` 并传 `city` + `keyword` |
| 金额单位 | `calculate-price` 返回金额为**分**，展示前需除以 100 |
| 响应格式 | 多数工具返回「字段说明 + JSON」混合文本，需先提取 JSON 再解析 |
| 限流 | 600 次/分钟/Token，超限返回 429；批量拆解套餐建议加间隔 |

## 本项目未使用的原因

- **领券类**（`available-coupons` / `auto-bind-coupons`）：属于账户变更操作，需用户明确同意；本项目默认只用本店已可用券
- **积分与商城类**（`query-my-account` / `mall-*` / 抽奖类）：与份量目标无关
- **派对预约类**：不属于日常点餐份量问题
- **售后类**（`cancel-order` / `query-order`）：当前范围为下单前决策
- **`query-meal-assistance` / `query-promotions`**：仅企业团餐场景
| 34 | `query-store-coupons` | Description: 查询【指定门店+订单类型】下可使用的优惠券，支持到店(orderType=1,含到店自取和得来速)和外送(orde | 已用 |
| 35 | `query-survey-coupon` | Description: 按订单号查询当前 MCP 用户本人订单的 CSAT 满意度答卷，并返回该订单关联奖券的标题、核销时间、核销状态和点 | 未使用 |
