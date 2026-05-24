import json
import re
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Union

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .models import StorySegment, GameConfig, WorldState, CustomTheme
from .prompt_loader import PromptLoader
from .world_state import WorldStateManager
from .npc_profile import NPCProfileManager
from .context_assembler import ContextAssembler


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")


class GameEngine:
    def __init__(self):
        self.prompt_loader = PromptLoader()
        self.world_manager = WorldStateManager()
        self.npc_manager = NPCProfileManager()
        self.context_assembler = ContextAssembler(
            self.prompt_loader, self.world_manager, self.npc_manager
        )
        self.games: dict[str, dict] = {}

    def create_game(self, config: GameConfig) -> tuple[str, list[StorySegment]]:
        game_id = uuid.uuid4().hex[:12]
        self.games[game_id] = {
            "config": config,
            "history": [],
            "genre": config.genre,
            "custom_theme": config.custom_theme.model_dump() if config.custom_theme else None,
        }
        self.world_manager.create(game_id)

        if config.genre == "custom" and config.custom_theme:
            intro_segments = self._generate_custom_intro(config.custom_theme)
        else:
            intro_segments = self._generate_intro(config.genre)

        self.world_manager.set_location(game_id, intro_segments.get("location", "unknown"))
        self.world_manager.update_history_summary(
            game_id, intro_segments.get("summary", "")
        )

        return game_id, intro_segments.get("segments", [])

    def _generate_intro(self, genre: str) -> dict:
        intros = {
            "fantasy": {
                "location": "低语森林",
                "summary": "你站在低语森林边缘。古老魔法在此沉睡。",
                "segments": [
                    StorySegment(type="environment", text="晨雾在林间缭绕。老橡树的根须扎入泥土深处。"),
                    StorySegment(type="narration", text="你站在低语森林入口。橡树村已在身后一日之遥。前方：未知。"),
                    StorySegment(type="system", text="输入动作开始冒险。四处看看、检查行囊，或踏入森林。")
                ]
            },
            "scifi": {
                "location": "轨道空间站 Nexus-7",
                "summary": "你停靠在 Nexus-7 空间站。这里是已知空间的边缘。",
                "segments": [
                    StorySegment(type="environment", text="对接舱能量嗡鸣。全息广告在舷窗外闪烁。锈红色行星的弧线填满视野。"),
                    StorySegment(type="narration", text="你的飞船锁定 Nexus-7 的 7 号泊位。信用点要赚，联系人要找，麻烦在等着你。"),
                    StorySegment(type="system", text="气闸门开启。你打算怎么做？")
                ]
            },
            "horror": {
                "location": "黑木精神病院",
                "summary": "你在废弃的精神病院中醒来。不记得怎么来的。",
                "segments": [
                    StorySegment(type="environment", text="荧光灯闪烁。油毡地上泛着病态绿光。空气中有铁锈和腐烂的气味。"),
                    StorySegment(type="narration", text="你在地板上醒来。头痛。最后的记忆是一片空白。走廊两侧是锈蚀的铁门。"),
                    StorySegment(type="system", text="走廊深处传来回声。调查、呼救，还是找出路？")
                ]
            },
            "wuxia": {
                "location": "玉龙客栈",
                "summary": "你抵达苍梧山脚的玉龙客栈。武林人士聚集之地。",
                "segments": [
                    StorySegment(type="environment", text="灯笼在晚风中摇曳。杯盏碰撞声和低语从屋内飘出。"),
                    StorySegment(type="narration", text="你走了三日才到此地。传言苍梧山顶有武林大会，神秘高人在寻传人。但消息总在酒香处流传最快。"),
                    StorySegment(type="system", text="掌柜朝你点头。进去坐坐、观察四周，还是上前搭话？")
                ]
            }
        }
        return intros.get(genre, intros["fantasy"])

    def _generate_custom_intro(self, theme: CustomTheme) -> dict:
        return {
            "location": theme.world_setting.split("，")[0] if "，" in theme.world_setting else theme.world_setting[:10],
            "summary": f"你进入了{theme.name}的世界。{theme.description}",
            "segments": [
                StorySegment(type="environment", text=f"{theme.world_setting}。空气中弥漫着未知的气息。"),
                StorySegment(type="narration", text=f"你踏入了{theme.name}的世界。{theme.description}。前方的路充满未知。"),
                StorySegment(type="system", text="你的冒险开始了。四处看看，或迈出第一步。")
            ]
        }

    async def generate_theme(self, user_hint: str = "") -> CustomTheme:
        prompt = f"""你是一个创意游戏设计师。请为一个文字冒险游戏生成一个独特的自定义主题。

{"用户提示：" + user_hint if user_hint else "请自由发挥创意，生成一个有趣且独特的主题。"}

要求：
1. 主题必须有趣、有深度、适合文字冒险游戏
2. 不要使用以下已有主题：奇幻、科幻、恐怖、武侠
3. 搜索全网热门的网络小说题材,并尝试使用其中的一个作为主题
请严格按以下JSON格式返回，不要添加任何额外文字或markdown标记：
{{
  "name": "主题名称（2-4个字）",
  "description": "一句话描述这个世界的核心设定（20-40字）",
  "world_setting": "世界观的详细描述（50-80字），包括时代背景、核心规则、独特元素",
  "narrative_style": "叙事风格描述（30-50字），包括氛围、节奏、语言特色",
  "icon": "一个代表这个主题的Unicode符号"
}}"""

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.9,
            "max_tokens": 5000,
            "response_format": {'type': 'json_object'},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            print("=" * 60, flush=True)
            print("[generate_theme] LLM raw response:", flush=True)
            print(content, flush=True)
            print("=" * 60, flush=True)

            theme_data = json.loads(content)
            return CustomTheme(**theme_data)

    def parse_segments(self, content: str) -> list[StorySegment]:
        content = content.strip()
        content = re.sub(r'^$', '', content)

        # Try to extract just the JSON array part
        json_match = re.search(r'(\[.*\])', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    segments = []
                    for item in data:
                        if isinstance(item, dict) and "type" in item and "text" in item:
                            segments.append(StorySegment(**item))
                    return segments
            except (json.JSONDecodeError, Exception):
                pass

        # Fallback: try parsing the full content
        try:
            data = json.loads(content)
            if isinstance(data, list):
                segments = []
                for item in data:
                    if isinstance(item, dict) and "type" in item and "text" in item:
                        segments.append(StorySegment(**item))
                return segments
        except json.JSONDecodeError:
            pass

        return [StorySegment(type="narration", text=content)]

    async def process_action(
        self, game_id: str, action: str
    ) -> AsyncGenerator[dict, None]:
        game = self.games.get(game_id)
        if not game:
            yield {"event": "error", "data": json.dumps({"error": "Game not found"})}
            return

        situations = self.context_assembler.detect_situations(
            action, game["history"]
        )
        messages = self.context_assembler.assemble(
            game_id, action, situations, game["history"], game["genre"],
            custom_theme=game.get("custom_theme")
        )

        print("=" * 80, flush=True)
        print("FULL PROMPT DUMP", flush=True)
        print("=" * 80, flush=True)
        for i, msg in enumerate(messages):
            role = msg["role"].upper()
            content = msg["content"]
            sep = "─" * 40
            print(f"\n{sep}", flush=True)
            print(f"  [{role}] Message #{i}", flush=True)
            print(f"{sep}", flush=True)
            print(content, flush=True)
        print("=" * 80, flush=True)
        print("END PROMPT DUMP", flush=True)
        print("=" * 80, flush=True)

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 5120,
            "top_p": 0.9,
            "response_format": {'type': 'json_object'},
        }

        buffer = ""
        segment_buffer = ""
        streaming_was_successful = False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield {"event": "error", "data": json.dumps({"error": f"API error {response.status_code}: {error_body.decode()}"})}
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    buffer += content
                                    segment_buffer += content

                                    segs = self._try_extract_segments(segment_buffer)
                                    if segs:
                                        for seg in segs:
                                            yield {"event": "segment", "data": seg.model_dump_json()}
                                        segment_buffer = self._clear_parsed(buffer)
                                        streaming_was_successful = True
                            except json.JSONDecodeError:
                                pass

            # Post-streaming: only parse if streaming extraction didn't fully succeed
            if buffer.strip() and not streaming_was_successful:
                remaining = buffer.strip()
                if remaining:
                    segs = self.parse_segments(remaining)
                    if segs:
                        for seg in segs:
                            yield {"event": "segment", "data": seg.model_dump_json()}

            # Parse final segments once (for history and state update)
            final_segments = self.parse_segments(buffer)
            response_text = json.dumps([s.model_dump() for s in final_segments])

            game["history"].append({
                "action": action,
                "response": response_text,
            })

            if len(game["history"]) > 30:
                game["history"] = game["history"][-30:]

            # Update world state from LLM output
            self.world_manager.update_from_narrative(game_id, final_segments)

            # Update NPC profiles from segments
            current_round = len(game["history"])
            for seg in final_segments:
                if seg.speaker and seg.npc_profile_update:
                    self.npc_manager.update_from_segment(
                        game_id, seg.speaker, seg.npc_profile_update, current_round
                    )
                elif seg.speaker and not self.npc_manager.get(game_id, seg.speaker):
                    from .models import NPCProfileUpdate
                    auto_update = NPCProfileUpdate(
                        key_event=seg.text[:50] if seg.text else None,
                        relation_change=0,
                    )
                    self.npc_manager.update_from_segment(
                        game_id, seg.speaker, auto_update, current_round
                    )

            world_state = self.world_manager.to_dict(game_id)
            npc_profiles = self.npc_manager.to_dict(game_id)
            yield {"event": "done", "data": json.dumps({"world_state": world_state, "npc_profiles": npc_profiles})}

        except httpx.ConnectError:
            yield {"event": "error", "data": json.dumps({"error": "Cannot connect to DeepSeek API. Check your network and API key."})}
        except httpx.TimeoutException:
            yield {"event": "error", "data": json.dumps({"error": "DeepSeek API timed out. Please try again."})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    def _try_extract_segments(self, text: str) -> list[StorySegment]:
        segments = []
        
        i = 0
        while i < len(text):
            if text[i] == '{':
                brace_depth = 0
                in_string = False
                escape_next = False
                obj_start = i
                
                for j in range(i, len(text)):
                    char = text[j]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\' and in_string:
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_depth += 1
                        elif char == '}':
                            brace_depth -= 1
                            if brace_depth == 0:
                                obj_str = text[obj_start:j+1]
                                try:
                                    data = json.loads(obj_str)
                                    if isinstance(data, dict) and "type" in data and "text" in data:
                                        segments.append(StorySegment(**data))
                                        i = j + 1
                                        break
                                except (json.JSONDecodeError, Exception):
                                    pass
                                i = j + 1
                                break
                        elif char == ']':
                            i = j + 1
                            break
                else:
                    i += 1
            elif text[i] == ']':
                i += 1
            else:
                i += 1
        
        return segments

    def _clear_parsed(self, buffer: str) -> str:
        last_obj_end = -1
        i = 0
        
        while i < len(buffer):
            if buffer[i] == '{':
                brace_depth = 0
                in_string = False
                escape_next = False
                obj_start = i
                
                for j in range(i, len(buffer)):
                    char = buffer[j]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\' and in_string:
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            brace_depth += 1
                        elif char == '}':
                            brace_depth -= 1
                            if brace_depth == 0:
                                obj_str = buffer[obj_start:j+1]
                                try:
                                    data = json.loads(obj_str)
                                    if isinstance(data, dict) and "type" in data and "text" in data:
                                        last_obj_end = j + 1
                                        i = j + 1
                                        break
                                except (json.JSONDecodeError, Exception):
                                    pass
                                i = j + 1
                                break
                        elif char == ']':
                            last_obj_end = j + 1
                            i = j + 1
                            break
                else:
                    i += 1
            elif buffer[i] == ']':
                last_obj_end = i + 1
                i += 1
            else:
                i += 1
        
        if last_obj_end > 0:
            return buffer[last_obj_end:]
        return buffer
