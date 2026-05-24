import re
from .models import WorldState, StorySegment


class WorldStateManager:
    def __init__(self):
        self._states: dict[str, WorldState] = {}

    def create(self, game_id: str) -> WorldState:
        state = WorldState()
        self._states[game_id] = state
        return state

    def get(self, game_id: str) -> WorldState:
        return self._states.get(game_id)

    def update_from_narrative(self, game_id: str, segments: list[StorySegment]):
        """Update world state by extracting state changes from LLM output segments."""
        state = self.get(game_id)
        if not state:
            return

        for seg in segments:
            if seg.state_update:
                su = seg.state_update
                state.hp = max(0, min(state.max_hp, state.hp + su.hp_change))
                state.max_hp = max(1, state.max_hp + su.max_hp_change)
                state.stamina = max(0, min(100, state.stamina + su.stamina_change))
                state.xp += su.xp_gain
                for item in su.add_items:
                    if isinstance(item, str):
                        if item not in state.inventory:
                            state.inventory.append(item)
                    else:
                        for _ in range(item.quantity):
                            state.inventory.append(item.name)
                for item in su.remove_items:
                    if item in state.inventory:
                        state.inventory.remove(item)
                if su.set_location:
                    state.location = su.set_location
                if su.set_flags:
                    state.flags.update(su.set_flags)
                for npc, delta in su.npc_relation_changes.items():
                    state.npc_relations[npc] = state.npc_relations.get(npc, 0) + delta

            text = seg.text or ""
            hp_loss = self._extract_hp_change(text)
            if hp_loss != 0:
                state.hp = max(0, min(state.max_hp, state.hp + hp_loss))

    def _extract_hp_change(self, text: str) -> int:
        patterns = [
            (r"受到?(\d+)点?伤害", -1),
            (r"损失?了?(\d+)点?生命", -1),
            (r"生命值?[减降低](\d+)", -1),
            (r"被?(?:击中|砍中|打中|刺中)", -15),
            (r"恢复了?(\d+)点?生命", 1),
            (r"回复了?(\d+)点?生命", 1),
            (r"生命值?[回恢]复?了?(\d+)", 1),
            (r"伤口?愈合", 20),
            (r"疗伤|治疗", 25),
        ]
        for pattern, default_delta in patterns:
            match = re.search(pattern, text)
            if match:
                if match.groups():
                    try:
                        return default_delta * abs(int(match.group(1)))
                    except ValueError:
                        return default_delta
                return default_delta
        return 0

    def add_item(self, game_id: str, item: str):
        state = self.get(game_id)
        if state and item not in state.inventory:
            state.inventory.append(item)

    def remove_item(self, game_id: str, item: str):
        state = self.get(game_id)
        if state and item in state.inventory:
            state.inventory.remove(item)

    def set_location(self, game_id: str, location: str):
        state = self.get(game_id)
        if state:
            state.location = location

    def set_flag(self, game_id: str, key: str, value: bool = True):
        state = self.get(game_id)
        if state:
            state.flags[key] = value

    def get_flag(self, game_id: str, key: str) -> bool:
        state = self.get(game_id)
        return state.flags.get(key, False) if state else False

    def add_xp(self, game_id: str, amount: int):
        state = self.get(game_id)
        if state:
            state.xp += amount

    def update_history_summary(self, game_id: str, summary: str):
        state = self.get(game_id)
        if state:
            state.history_summary = summary

    def to_dict(self, game_id: str) -> dict:
        state = self.get(game_id)
        if state:
            return state.model_dump()
        return {}
