from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChatState:
    mode: str
    last_reply_at: float = 0.0


class SubscriptionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_chat_states(self, default_mode: str) -> dict[int, ChatState]:
        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        if "chats" in raw_data:
            chats = raw_data.get("chats", {})
            states: dict[int, ChatState] = {}
            for raw_chat_id, payload in chats.items():
                if not isinstance(payload, dict):
                    continue
                chat_id = int(raw_chat_id)
                states[chat_id] = ChatState(
                    mode=str(payload.get("mode", default_mode)),
                    last_reply_at=float(payload.get("last_reply_at", 0.0)),
                )
            return states

        chat_ids = raw_data.get("chat_ids", [])
        return {int(chat_id): ChatState(mode=default_mode) for chat_id in chat_ids}

    def save_chat_states(self, chat_states: dict[int, ChatState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chats": {
                str(chat_id): {
                    "mode": state.mode,
                    "last_reply_at": state.last_reply_at,
                }
                for chat_id, state in sorted(chat_states.items())
            }
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)
