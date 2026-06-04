# TOOLS · 环境配置

## 脚本运行环境
- Python: 3.11+, 标准库 + requests
- 所有脚本路径相对于工作区根目录
- 脚本输出为JSON格式

## Mock API
- 地址: http://localhost:8010
- 启动: `cd mock-backend && python app.py`
- 端口冲突时: `python app.py --port 8011`

## 飞书集成
- 模式: Webhook(演示) / API(生产)
- Webhook URL: 通过环境变量 FEISHU_WEBHOOK_URL 配置
- 卡片类型: dining_card, queue_card, commute_card, leisure_card

## 网络搜索源
| 数据类型 | 搜索源 | 来源标签 |
|---------|--------|---------|
| 餐厅/排队 | 大众点评、美团 | [大众点评] [美团] |
| 天气 | 中国天气网 | [天气网] |
| 活动/电影 | 猫眼、大麦 | [猫眼] [大麦] |
| 路线/打车 | 高德地图 | [高德] |
| 外卖/优惠 | 美团外卖 | [美团外卖] |
| 用户攻略 | 小红书 | [小红书] |

## 文件路径
- 用户数据: `data/` (Mock数据种子)
- 临时文件: 系统临时目录
- 记忆日志: `memory/`
