from pydantic import BaseModel
from typing import List, Optional, Literal, Union


SegmentType = Literal[
    "narration", "dialogue", "action", "environment",
    "important", "thought", "combat", "item", "system",
    "state_update"
]


class AddItem(BaseModel):
    name: str
    quantity: int = 1


class StateUpdate(BaseModel):
    hp_change: int = 0
    max_hp_change: int = 0
    stamina_change: int = 0
    xp_gain: int = 0
    add_items: List[Union[str, AddItem]] = []
    remove_items: List[str] = []
    set_location: Optional[str] = None
    set_flags: dict = {}
    npc_relation_changes: dict = {}


class NPCProfileUpdate(BaseModel):
    appearance: Optional[str] = None
    personality: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    key_event: Optional[str] = None
    relation_change: int = 0


class NPCProfile(BaseModel):
    name: str
    appearance: str = ""
    personality: str = ""
    role: str = ""
    location: str = ""
    relation: int = 0
    encounters: int = 0
    key_events: List[str] = []
    first_seen_round: int = 0
    last_seen_round: int = 0


class StorySegment(BaseModel):
    type: SegmentType
    text: str
    speaker: Optional[str] = None
    state_update: Optional[StateUpdate] = None
    npc_profile_update: Optional[NPCProfileUpdate] = None


class CustomTheme(BaseModel):
    name: str
    description: str
    world_setting: str
    narrative_style: str
    icon: str = "✧"


class GameConfig(BaseModel):
    genre: Literal["fantasy", "scifi", "horror", "wuxia", "custom"]
    player_name: str = "Adventurer"
    custom_theme: Optional[CustomTheme] = None


class PlayerAction(BaseModel):
    action: str


class CreateGameResponse(BaseModel):
    game_id: str
    intro: str


class StoryResponse(BaseModel):
    segments: List[StorySegment]


class WorldState(BaseModel):
    hp: int = 100
    max_hp: int = 100
    stamina: int = 100
    level: int = 1
    xp: int = 0
    inventory: List[str] = []
    location: str = "unknown"
    history_summary: str = ""
    flags: dict = {}
    npc_relations: dict = {}
