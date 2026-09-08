"""Typed character abilities and their activation timing."""

import enum
from dataclasses import dataclass
from typing import TypeAlias


class AbilityType(enum.StrEnum):
    """Color category controlling how a character ability behaves."""

    NONE = "none"
    RED = "red"
    BLUE = "blue"


class AbilityTiming(enum.StrEnum):
    """Turn phase in which a blue ability applies."""

    BEFORE_TURN = "before_turn"
    DURING_TURN = "during_turn"
    AFTER_TURN = "after_turn"
    PERSISTENT = "persistent"


@dataclass(frozen=True, slots=True)
class VirtualPearlAbility:
    """Provide one virtual pearl with one of the listed effective values.

    The values are alternative interpretations of one resource. Consequently,
    one activated character can provide at most one virtual pearl to each
    activation, including a wildcard provider such as Fuchur.

    Attributes:
        values: Effective pearl values the virtual resource may represent.
        timing: Turn phase in which the resource is available.
    """

    values: tuple[int, ...]
    timing: AbilityTiming = AbilityTiming.DURING_TURN

    def __post_init__(self) -> None:
        """Validate the virtual values and timing."""
        if not self.values or any(not 1 <= value <= 8 for value in self.values):
            message = "virtual pearl values must be from 1 through 8"
            raise ValueError(message)
        if len(set(self.values)) != len(self.values):
            message = "virtual pearl values must be unique"
            raise ValueError(message)
        if not isinstance(self.timing, AbilityTiming):
            message = "ability timing must be an AbilityTiming member"
            raise TypeError(message)


CharacterAbility: TypeAlias = VirtualPearlAbility
