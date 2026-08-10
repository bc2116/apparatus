"""Structured setup-interview answers and deterministic starter-record seeds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PersonSeed:
    name: str
    role: str | None
    organization: str | None


@dataclass(frozen=True)
class GoalSeed:
    title: str
    done_when: str
    next_action: str
    status: str


def person_seeds(profile: dict[str, Any]) -> tuple[PersonSeed, ...]:
    """Return profile people in profile order after records validation has passed."""
    return tuple(
        PersonSeed(
            name=entry["name"],
            role=entry.get("role"),
            organization=entry.get("organization"),
        )
        for entry in profile.get("key_people", [])
    )


def goal_seeds(profile: dict[str, Any]) -> tuple[GoalSeed, ...]:
    """Derive valid goal fields without inventing an unstated completion oracle."""
    seeds: list[GoalSeed] = []
    for entry in profile.get("current_efforts", []):
        done_when = entry.get("done_when")
        if done_when is None:
            seeds.append(
                GoalSeed(
                    title=entry["title"],
                    done_when="Agree with the owner what done looks like.",
                    next_action="Agree with the owner what done looks like.",
                    status="waiting",
                )
            )
            continue
        seeds.append(
            GoalSeed(
                title=entry["title"],
                done_when=done_when,
                next_action=entry.get(
                    "next_action", "Agree with the owner on the next action."
                ),
                status="active",
            )
        )
    return tuple(seeds)
