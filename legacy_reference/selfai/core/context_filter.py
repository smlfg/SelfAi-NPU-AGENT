from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


# Grundlegende Schlagwortzuordnung für Tags/Intents.
KEYWORD_TAG_MAP: dict[str, Sequence[str]] = {
    "calendar": [
        "calendar",
        "schedule",
        "termin",
        "meeting",
        "appointment",
        "event",
        "eintragen",
        "kalender",
    ],
    "travel": [
        "travel",
        "flight",
        "flug",
        "train",
        "reise",
        "ticket",
        "bahnhof",
        "airline",
        "hotel",
    ],
    "code": [
        "code",
        "funktion",
        "function",
        "implement",
        "bug",
        "fix",
        "python",
        "javascript",
        "programmieren",
        "algorithm",
        "test",
    ],
    "math": [
        "calculate",
        "berechne",
        "sum",
        "difference",
        "percentage",
        "steuer",
        "tax",
        "prozent",
    ],
    "file": [
        "file",
        "read",
        "write",
        "path",
        "ordner",
        "directory",
        "datei",
        "projekt",
        "repo",
    ],
    "memory": [
        "context",
        "memory",
        "history",
        "verlauf",
        "kontext",
    ],
    "communication": [
        "email",
        "message",
        "mail",
        "reply",
        "antwort",
        "brief",
        "nachricht",
    ],
    "negotiation": [
        "verhandlung",
        "deal",
        "agreement",
        "contract",
        "mediation",
        "conflict",
    ],
}


AGENT_TAG_HINTS: dict[str, Sequence[str]] = {
    "code_helfer": ["code"],
    "projektmanager": ["calendar", "planning"],
    "verhandlungspartner": ["negotiation"],
    "reiseplaner": ["travel"],
}


@dataclass(frozen=True)
class TaskClassification:
    intent: str
    tags: List[str]


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def extract_tags(text: str, fallback_tags: Iterable[str] | None = None) -> List[str]:
    """
    Ermittelt heuristische Tags aus einem Text mithilfe einer einfachen Keyword-Liste.
    """
    text_normalized = _normalize(text)
    tags: set[str] = set()

    for tag, keywords in KEYWORD_TAG_MAP.items():
        for keyword in keywords:
            if keyword in text_normalized:
                tags.add(tag)
                break

    if fallback_tags:
        for item in fallback_tags:
            clean = _normalize(item)
            if clean:
                tags.add(clean)

    if not tags:
        tags.add("general")

    return sorted(tags)


def classify_task(text: str, agent_key: str | None = None) -> TaskClassification:
    """
    Sehr einfache Intent/TAG-Heuristik:
    Nutzt aktuell nur Tags; Intent entspricht dem „größten“ Tag.
    """
    normalized = _normalize(text)
    fallback = []
    if agent_key:
        fallback.extend(AGENT_TAG_HINTS.get(agent_key, []))

    tags = extract_tags(normalized, fallback_tags=fallback)
    intent = tags[0] if tags else "general"
    return TaskClassification(intent=intent, tags=tags)


def calculate_relevance(current_tags: Iterable[str], candidate_tags: Iterable[str]) -> float:
    """
    Jaccard-Similarity zwischen zwei Tag-Mengen.
    """
    current = {tag.lower() for tag in current_tags if tag}
    candidate = {tag.lower() for tag in candidate_tags if tag}

    if not current or not candidate:
        return 0.0

    intersection = current & candidate
    union = current | candidate

    if not union:
        return 0.0

    return len(intersection) / len(union)
