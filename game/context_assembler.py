from .prompt_loader import PromptLoader
from .world_state import WorldStateManager
from .npc_profile import NPCProfileManager
from .models import WorldState

COMBAT_KEYWORDS = [
    "attack", "strike", "fight", "slash", "shoot", "punch", "kick",
    "draw", "unsheathe", "fire", "cast", "combat", "battle",
    "defend", "parry", "dodge", "charge", "assault"
]

DIALOGUE_KEYWORDS = [
    "say", "ask", "tell", "speak", "talk", "converse", "question",
    "demand", "persuade", "bargain", "negotiate", "greet", "shout",
    "whisper", "call", "yell"
]

EXPLORATION_KEYWORDS = [
    "look", "examine", "search", "investigate", "explore", "go",
    "walk", "run", "enter", "leave", "approach", "climb", "open",
    "move", "travel", "cross", "follow", "sneak", "creep"
]

PUZZLE_KEYWORDS = [
    "solve", "puzzle", "riddle", "mechanism", "lock", "key",
    "code", "pattern", "lever", "switch", "pressure", "plate",
    "glyph", "symbol", "inscription"
]


class ContextAssembler:
    def __init__(self, prompt_loader: PromptLoader, world_manager: WorldStateManager, npc_manager: NPCProfileManager):
        self.loader = prompt_loader
        self.world = world_manager
        self.npc_manager = npc_manager

    def _build_custom_genre_prompt(self, theme: dict) -> str:
        parts = [f"流派：{theme.get('name', '自定义')}"]
        parts.append("")
        parts.append("世界观：")
        for line in theme.get("world_setting", "").split("。"):
            line = line.strip()
            if line:
                parts.append(f"- {line}")
        parts.append("")
        parts.append("叙事风格：")
        for line in theme.get("narrative_style", "").split("。"):
            line = line.strip()
            if line:
                parts.append(f"- {line}")
        if theme.get("description"):
            parts.append("")
            parts.append(f"核心设定：{theme['description']}")
        return "\n".join(parts)

    def detect_situations(self, action: str, history: list) -> list[str]:
        import re
        action_lower = action.lower()
        situations = set()

        # Use word boundary matching for more accuracy
        if any(re.search(r'\b' + re.escape(kw) + r'\b', action_lower) for kw in COMBAT_KEYWORDS):
            situations.add("combat")
        if any(re.search(r'\b' + re.escape(kw) + r'\b', action_lower) for kw in DIALOGUE_KEYWORDS):
            situations.add("dialogue")
        if any(re.search(r'\b' + re.escape(kw) + r'\b', action_lower) for kw in EXPLORATION_KEYWORDS):
            situations.add("exploration")
        if any(re.search(r'\b' + re.escape(kw) + r'\b', action_lower) for kw in PUZZLE_KEYWORDS):
            situations.add("puzzle")

        if not situations:
            situations.add("exploration")

        return sorted(situations)

    def _format_history_response(self, response_json: str) -> str:
        """Convert stored JSON response back to readable narrative text."""
        import json
        try:
            segments = json.loads(response_json)
            if isinstance(segments, list):
                texts = []
                for s in segments:
                    if isinstance(s, dict):
                        text = s.get("text", "")
                        if s.get("speaker"):
                            text = f"[{s['speaker']}] {text}"
                        texts.append(text)
                return "\n".join(texts)
        except (json.JSONDecodeError, Exception):
            pass
        return response_json

    def assemble(
        self,
        game_id: str,
        action: str,
        situations: list[str],
        history: list,
        genre: str,
        custom_theme: dict = None
    ) -> list[dict]:
        messages = []

        core = self.loader.load_core()

        if genre == "custom" and custom_theme:
            genre_content = self._build_custom_genre_prompt(custom_theme)
        else:
            genre_content = self.loader.load_genre(genre)

        system_parts = [core]
        if genre_content:
            system_parts.append(genre_content)

        for sit in situations:
            sit_content = self.loader.load_situation(sit)
            if sit_content:
                system_parts.append(sit_content)

        system_message = "\n\n---\n\n".join(system_parts)
        messages.append({"role": "system", "content": system_message})

        world_state = self.world.to_dict(game_id)
        if world_state:
            world_context = f"[Current State] Location: {world_state.get('location', 'unknown')} | HP: {world_state.get('hp', 100)}/{world_state.get('max_hp', 100)} | Inventory: {', '.join(world_state.get('inventory', [])) or 'empty'}"
            messages.append({"role": "system", "content": world_context})

        if world_state.get('history_summary'):
            messages.append({
                "role": "system",
                "content": f"[Story So Far] {world_state['history_summary']}"
            })

        matched_npcs = self.npc_manager.find_matching_npcs(game_id, action)
        if matched_npcs:
            npc_parts = []
            for profile in matched_npcs:
                npc_parts.append(self.npc_manager.format_profile_for_context(profile))
            npc_context = "\n\n".join(npc_parts)
            messages.append({
                "role": "system",
                "content": f"[Known NPCs in Current Scene]\n{npc_context}\n\nStay consistent with these NPC profiles. Reference their past interactions and maintain their personality."
            })

        recent = history[-6:] if len(history) > 6 else history
        for entry in recent:
            messages.append({"role": "user", "content": entry["action"]})
            # Convert stored JSON response to readable text
            readable = self._format_history_response(entry["response"])
            messages.append({"role": "assistant", "content": readable})

        messages.append({"role": "user", "content": action})

        return messages
