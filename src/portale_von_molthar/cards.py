"""Card value objects for Die Portale von Molthar."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PearlCard:
    """A numbered pearl card."""

    value: int

    def __post_init__(self) -> None:
        """Validate the pearl value."""
        if not 1 <= self.value <= 8:
            message = "A pearl card value must be between 1 and 8."
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class CharacterCard:
    """A character card without a special effect.

    Attributes:
        name: Name used to identify the character.
        requirements: Pearl values needed to activate the character.
        power_points: Power points awarded by the character.
    """

    name: str
    requirements: tuple[int, ...]
    power_points: int

    def __post_init__(self) -> None:
        """Validate the card's basic printed values."""
        if not self.name:
            message = "A character card must have a name."
            raise ValueError(message)
        if not self.requirements:
            message = "A character card must have at least one pearl requirement."
            raise ValueError(message)
        if any(value < 1 or value > 8 for value in self.requirements):
            message = "Character pearl requirements must be between 1 and 8."
            raise ValueError(message)
        if self.power_points < 0:
            message = "Character power points cannot be negative."
            raise ValueError(message)
