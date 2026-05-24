# StoryForge Backend

AI 驱动的文字冒险游戏后端服务，基于 FastAPI + DeepSeek API。

## 技术栈

- **Python 3.12+** / **FastAPI** — API 服务
- **SSE (Server-Sent Events)** — 流式响应
- **DeepSeek Chat API** — LLM 驱动
- **httpx** — 异步 HTTP 客户端

## 目录结构

```
backend/
├── main.py                  # FastAPI 入口，路由定义
├── requirements.txt         # Python 依赖
├── .env                     # 环境变量（API Key 等）
├── game/
│   ├── engine.py            # 核心引擎：游戏生命周期、LLM 调用、SSE 流式解析
│   ├── models.py            # Pydantic 模型定义
│   ├── world_state.py       # 世界状态管理
│   ├── context_assembler.py # 情境检测 + Prompt 组装
│   └── prompt_loader.py     # Prompt 文件加载器（带缓存）
└── prompts/
    ├── core/
    │   ├── system.md        # 系统指令（格式、行为约束）
    │   └── narrative_style.md
    ├── genres/              # 流派风格（fantasy/scifi/horror/wuxia）
    └── situations/          # 情境指令（combat/dialogue/exploration/puzzle）
```

## 开发

```bash
cd backend
pip install -r requirements.txt
# 配置 .env: DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
python main.py
```

服务启动在 `http://localhost:8000`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/game/new` | 创建新游戏 |
| GET | `/api/game/{game_id}` | 获取游戏状态 |
| POST | `/api/game/{game_id}/act` | 执行动作（SSE 流式响应） |

### `/api/game/new`

```json
{ "genre": "fantasy", "player_name": "云逸" }
```

### `/api/game/{game_id}/act`

返回 SSE 事件流：
- `event: segment` — 故事片段
- `event: done` — 完成（附带世界状态）
- `event: error` — 错误

## 核心设计

- **情境检测**: 根据玩家输入关键词自动匹配 combat/dialogue/exploration/puzzle 情境，动态组装 prompt
- **流式解析**: SSE 流式接收 LLM 输出，实时解析 JSON 片段并推送
- **世界状态**: LLM 返回的 `state_update` 字段驱动 HP/物品/位置等变化；同时用正则从文本中二次提取
- **历史管理**: 保留最近 30 轮对话，超出则截断
