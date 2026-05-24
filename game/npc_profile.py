from .models import NPCProfile, NPCProfileUpdate


class NPCProfileManager:
    def __init__(self):
        self._profiles: dict[str, dict[str, NPCProfile]] = {}

    def _ensure_game(self, game_id: str):
        if game_id not in self._profiles:
            self._profiles[game_id] = {}

    def get(self, game_id: str, npc_name: str) -> NPCProfile | None:
        return self._profiles.get(game_id, {}).get(npc_name)

    def get_all(self, game_id: str) -> dict[str, NPCProfile]:
        return self._profiles.get(game_id, {})

    def upsert(self, game_id: str, profile: NPCProfile):
        self._ensure_game(game_id)
        self._profiles[game_id][profile.name] = profile

    def update_from_segment(
        self,
        game_id: str,
        npc_name: str,
        update: NPCProfileUpdate,
        current_round: int,
    ):
        self._ensure_game(game_id)
        existing = self._profiles[game_id].get(npc_name)

        if existing:
            if update.appearance:
                existing.appearance = update.appearance
            if update.personality:
                existing.personality = update.personality
            if update.role:
                existing.role = update.role
            if update.location:
                existing.location = update.location
            if update.key_event:
                existing.key_events.append(update.key_event)
                if len(existing.key_events) > 10:
                    existing.key_events = existing.key_events[-10:]
            existing.relation = max(-100, min(100, existing.relation + update.relation_change))
            existing.encounters += 1
            existing.last_seen_round = current_round
        else:
            profile = NPCProfile(
                name=npc_name,
                appearance=update.appearance or "",
                personality=update.personality or "",
                role=update.role or "",
                location=update.location or "",
                relation=max(-100, min(100, update.relation_change)),
                encounters=1,
                key_events=[update.key_event] if update.key_event else [],
                first_seen_round=current_round,
                last_seen_round=current_round,
            )
            self._profiles[game_id][npc_name] = profile

    def extract_npc_name(self, action: str) -> str | None:
        import re
        patterns = [
            r"和(.+?)(?:说话|交谈|对话|聊天|搭话|问|谈)",
            r"向(.+?)(?:说话|询问|打招呼|搭话|问|请求)",
            r"跟(.+?)(?:说话|交谈|对话|聊天|搭话|问)",
            r"找(.+?)(?:说话|交谈|对话|聊天|搭话|问)",
            r"对(.+?)(?:说|喊|低语|耳语|点头|微笑)",
            r"与(.+?)(?:交谈|对话|战斗|交手)",
            r"(?:攻击|击打|防御|躲避)(.+?)(?:的|了|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, action)
            if match:
                name = match.group(1).strip()
                if 1 <= len(name) <= 10:
                    return name
        return None

    def find_matching_npcs(self, game_id: str, action: str) -> list[NPCProfile]:
        known_npcs = self.get_all(game_id)
        if not known_npcs:
            return []

        matched = []
        action_lower = action.lower()

        for name, profile in known_npcs.items():
            if name in action:
                matched.append(profile)
                continue

            for key_event in profile.key_events:
                if any(c in action for c in key_event[:4]):
                    matched.append(profile)
                    break

        extracted_name = self.extract_npc_name(action)
        if extracted_name and extracted_name in known_npcs:
            profile = known_npcs[extracted_name]
            if profile not in matched:
                matched.append(profile)

        return matched

    def format_profile_for_context(self, profile: NPCProfile) -> str:
        parts = [f"[NPC: {profile.name}]"]
        if profile.appearance:
            parts.append(f"  外貌: {profile.appearance}")
        if profile.personality:
            parts.append(f"  性格: {profile.personality}")
        if profile.role:
            parts.append(f"  身份: {profile.role}")
        if profile.location:
            parts.append(f"  位置: {profile.location}")

        relation_desc = self._relation_label(profile.relation)
        parts.append(f"  与你关系: {relation_desc}({profile.relation})")
        parts.append(f"  互动次数: {profile.encounters}")

        if profile.key_events:
            parts.append(f"  重要经历: {'; '.join(profile.key_events[-5:])}")

        return "\n".join(parts)

    def _relation_label(self, value: int) -> str:
        if value >= 60:
            return "挚友"
        elif value >= 30:
            return "友好"
        elif value >= 10:
            return "友善"
        elif value >= -10:
            return "一般"
        elif value >= -30:
            return "冷淡"
        elif value >= -60:
            return "敌视"
        else:
            return "死敌"

    def to_dict(self, game_id: str) -> dict:
        profiles = self.get_all(game_id)
        return {name: p.model_dump() for name, p in profiles.items()}

    def load_from_dict(self, game_id: str, data: dict):
        self._ensure_game(game_id)
        for name, profile_data in data.items():
            self._profiles[game_id][name] = NPCProfile(**profile_data)
