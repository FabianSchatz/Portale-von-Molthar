"""State owned by one Molthar player."""

from dataclasses import dataclass, field

from portale_von_molthar.cards import CharacterCard, PearlCard


@dataclass(slots=True)
class PlayerState:
    """The cards belonging to one player."""

    pearl_cards: list[PearlCard] = field(default_factory=list)
    portal: list[CharacterCard] = field(default_factory=list)
    activated_characters: list[CharacterCard] = field(default_factory=list)

    @property
    def power_points(self) -> int:
        """Return the power points from activated characters."""
        return sum(card.power_points for card in self.activated_characters)
