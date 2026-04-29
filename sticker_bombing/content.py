from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Mode:
    name: str
    title: str
    description: str
    phrases: tuple[str, ...]


@dataclass(frozen=True)
class Trigger:
    name: str
    keywords: tuple[str, ...]
    phrases: tuple[str, ...]


class PhraseBook:
    def __init__(
        self,
        base_phrases: list[str],
        modes: dict[str, Mode] | None = None,
        triggers: list[Trigger] | None = None,
    ) -> None:
        cleaned_base = self._clean_phrases(base_phrases)
        self._base_phrases = cleaned_base
        self._modes = modes or {
            "classic": Mode(
                name="classic",
                title="Классика",
                description="Базовый режим с фирменными репликами.",
                phrases=tuple(cleaned_base),
            )
        }
        self._triggers = triggers or []

    @classmethod
    def from_yaml(cls, path: str) -> "PhraseBook":
        with Path(path).open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        phrases = data.get("memes", [])
        if not isinstance(phrases, list):
            raise ValueError("memes.yaml должен содержать список в ключе 'memes'.")

        modes = cls._load_modes(data.get("modes", {}), phrases)
        triggers = cls._load_triggers(data.get("triggers", {}))
        return cls([str(item) for item in phrases], modes=modes, triggers=triggers)

    def random_phrase(self, mode_name: str = "classic") -> str | None:
        phrases = self.phrases_for_mode(mode_name)
        if not phrases:
            return None
        return random.choice(phrases)

    def has_trigger(self, text: str) -> bool:
        normalized = text.casefold()
        return any(
            any(keyword in normalized for keyword in trigger.keywords)
            for trigger in self._triggers
        )

    def default_mode(self) -> str:
        if "classic" in self._modes:
            return "classic"
        return next(iter(self._modes))

    def has_mode(self, mode_name: str) -> bool:
        return mode_name in self._modes

    def get_mode(self, mode_name: str) -> Mode:
        if mode_name in self._modes:
            return self._modes[mode_name]
        return self._modes[self.default_mode()]

    def list_modes(self) -> list[Mode]:
        return list(self._modes.values())

    def phrases_for_mode(self, mode_name: str) -> tuple[str, ...]:
        mode = self.get_mode(mode_name)
        return mode.phrases

    def __len__(self) -> int:
        return len(self._base_phrases)

    @staticmethod
    def _clean_phrases(phrases: list[str]) -> list[str]:
        return [phrase.strip() for phrase in phrases if phrase and phrase.strip()]

    @classmethod
    def _load_modes(cls, raw_modes: object, base_phrases: list[str]) -> dict[str, Mode]:
        if raw_modes is None:
            raw_modes = {}
        if not isinstance(raw_modes, dict):
            raise ValueError("Ключ 'modes' в memes.yaml должен быть объектом.")

        modes: dict[str, Mode] = {
            "classic": Mode(
                name="classic",
                title="Классика",
                description="Базовый режим с фирменными репликами.",
                phrases=tuple(cls._clean_phrases([str(item) for item in base_phrases])),
            )
        }

        for name, payload in raw_modes.items():
            if not isinstance(payload, dict):
                raise ValueError(f"Режим '{name}' должен быть объектом.")
            phrases = payload.get("phrases", [])
            if not isinstance(phrases, list):
                raise ValueError(f"Режим '{name}' должен содержать список phrases.")
            cleaned_phrases = tuple(cls._clean_phrases([str(item) for item in phrases]))
            if not cleaned_phrases:
                continue
            modes[str(name)] = Mode(
                name=str(name),
                title=str(payload.get("title", name)),
                description=str(payload.get("description", "")),
                phrases=cleaned_phrases,
            )

        return modes

    @classmethod
    def _load_triggers(cls, raw_triggers: object) -> list[Trigger]:
        if raw_triggers is None:
            return []
        if not isinstance(raw_triggers, dict):
            raise ValueError("Ключ 'triggers' в memes.yaml должен быть объектом.")

        triggers: list[Trigger] = []
        for name, payload in raw_triggers.items():
            if not isinstance(payload, dict):
                raise ValueError(f"Триггер '{name}' должен быть объектом.")
            keywords = payload.get("keywords", [])
            phrases = payload.get("phrases", [])
            if not isinstance(keywords, list) or not isinstance(phrases, list):
                raise ValueError(f"Триггер '{name}' должен содержать списки keywords и phrases.")
            cleaned_keywords = tuple(
                keyword.casefold().strip()
                for keyword in (str(item) for item in keywords)
                if keyword.strip()
            )
            cleaned_phrases = tuple(cls._clean_phrases([str(item) for item in phrases]))
            if cleaned_keywords and cleaned_phrases:
                triggers.append(
                    Trigger(
                        name=str(name),
                        keywords=cleaned_keywords,
                        phrases=cleaned_phrases,
                    )
                )

        return triggers
