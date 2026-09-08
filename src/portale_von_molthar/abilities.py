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
class GainActionsAbility:
    """Immediately grant additional actions when the character is activated.

    Attributes:
        actions: Number of actions added to the current turn.
    """

    actions: int

    def __post_init__(self) -> None:
        """Validate the number of granted actions."""
        if self.actions <= 0:
            message = "an action-granting ability must add at least one action"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class NeighborActivationAbility:
    """Allow neighboring players to activate this character from its owner's portal."""


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


@dataclass(frozen=True, slots=True)
class PearlValueSubstitutionAbility:
    """Allow a physical pearl value to represent additional effective values.

    Every matching hand card remains one physical payment resource and is
    discarded by its printed value. The additional values are mutually
    exclusive interpretations of that resource.

    Attributes:
        printed_value: Value printed on each affected physical pearl card.
        effective_values: Additional values an affected card may represent.
        timing: Turn phase in which the substitution is available.
    """

    printed_value: int
    effective_values: tuple[int, ...]
    timing: AbilityTiming = AbilityTiming.DURING_TURN

    def __post_init__(self) -> None:
        """Validate the printed value, additional values, and timing."""
        if not 1 <= self.printed_value <= 8:
            message = "the substituted printed pearl value must be from 1 through 8"
            raise ValueError(message)
        if not self.effective_values or any(not 1 <= value <= 8 for value in self.effective_values):
            message = "substituted effective pearl values must be from 1 through 8"
            raise ValueError(message)
        if self.printed_value in self.effective_values:
            message = "substitutions only list values different from the printed value"
            raise ValueError(message)
        if len(set(self.effective_values)) != len(self.effective_values):
            message = "substituted effective pearl values must be unique"
            raise ValueError(message)
        if not isinstance(self.timing, AbilityTiming):
            message = "ability timing must be an AbilityTiming member"
            raise TypeError(message)


CharacterAbility: TypeAlias = (
    GainActionsAbility
    | NeighborActivationAbility
    | VirtualPearlAbility
    | PearlValueSubstitutionAbility
)
