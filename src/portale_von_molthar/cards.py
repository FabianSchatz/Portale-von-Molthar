"""Structured data for implemented character cards."""

from dataclasses import dataclass
from typing import Final

from portale_von_molthar.abilities import (
    AbilityType,
    CharacterAbility,
    GainActionsAbility,
    NeighborActivationAbility,
    PearlValueSubstitutionAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.requirements import (
    AllOf,
    AnyOf,
    ExactValues,
    FixedCountSum,
    Parity,
    ParityValues,
    Requirement,
    SameValue,
)


@dataclass(frozen=True, slots=True)
class Character:
    """A character card with rewards and a typed activation requirement.

    Attributes:
        id: Stable identifier matching `docs/character_cards.md`.
        requirement: Pearl requirement paid on activation.
        points: Power points awarded on activation.
        copies: Number of copies of this card in the character deck.
        diamonds: Diamonds awarded to the player on activation.
        diamonds_cost: Diamonds the player must additionally pay to activate
            (RULES.md section 8.2), on top of `requirement`.
        ability_type: Whether the character has no ability or a red or blue one.
        ability: Structured special ability, if the character has one.
    """

    id: str
    requirement: Requirement
    points: int
    copies: int
    diamonds: int = 0
    diamonds_cost: int = 0
    ability_type: AbilityType = AbilityType.NONE
    ability: CharacterAbility | None = None

    def __post_init__(self) -> None:
        """Validate rewards and agreement between ability data and color."""
        if self.points < 0 or self.copies <= 0 or self.diamonds < 0 or self.diamonds_cost < 0:
            message = "points and diamonds must be nonnegative and copies must be positive"
            raise ValueError(message)
        if not isinstance(self.ability_type, AbilityType):
            message = "ability type must be an AbilityType member"
            raise TypeError(message)
        if (self.ability_type is AbilityType.NONE) != (self.ability is None):
            message = "characters without an ability need type NONE and all abilities need a type"
            raise ValueError(message)
        if (
            isinstance(
                self.ability,
                (PearlValueSubstitutionAbility, VirtualPearlAbility),
            )
            and self.ability_type is not AbilityType.BLUE
        ):
            message = "persistent pearl abilities must belong to blue characters"
            raise ValueError(message)
        if (
            isinstance(self.ability, (GainActionsAbility, NeighborActivationAbility))
            and self.ability_type is not AbilityType.RED
        ):
            message = "one-time abilities must belong to red characters"
            raise ValueError(message)


# Implemented cards from docs/character_cards.md.
CHARACTERS: Final = (
    Character("goblin", SameValue(2), points=1, copies=3),
    Character("fluffy", SameValue(3), points=2, copies=2),
    Character("lion", ExactValues((8, 8, 8, 8)), points=5, copies=1),
    Character("dwarf", ExactValues((6, 6, 8, 8)), points=3, copies=3),
    Character("hansel_and_gretel", ExactValues((8, 8)), points=2, copies=2),
    Character("frau_holle", ExactValues((7, 7, 7, 7)), points=4, copies=2),
    Character("groot", SameValue(4), points=3, copies=1),
    Character(
        "bilbo_odd",
        ParityValues(3, Parity.ODD),
        points=1,
        copies=1,
        diamonds=1,
    ),
    Character(
        "bilbo_even",
        ParityValues(3, Parity.EVEN),
        points=1,
        copies=1,
        diamonds=1,
    ),
    Character(
        "gnome",
        AllOf((SameValue(2), ExactValues((6, 6)))),
        points=2,
        copies=2,
        diamonds=1,
    ),
    Character(
        "captain_hook",
        ExactValues((2, 2, 2)),
        points=3,
        copies=1,
        diamonds_cost=1,
    ),
    Character("terminator", FixedCountSum(3, 20), points=2, copies=1),
    Character("unicorn", ExactValues((1, 2, 3, 4)), points=1, copies=1, diamonds=2),
    Character("trump", ExactValues((7, 7, 8, 8)), points=3, copies=2, diamonds=1),
    Character(
        "irrlicht_1",
        AnyOf((ExactValues((3, 3, 3)), ExactValues((6, 6, 6)))),
        points=3,
        copies=1,
        ability_type=AbilityType.RED,
        ability=NeighborActivationAbility(),
    ),
    Character(
        "irrlicht_2",
        AnyOf((ExactValues((4, 4, 4)), ExactValues((5, 5, 5)))),
        points=3,
        copies=1,
        ability_type=AbilityType.RED,
        ability=NeighborActivationAbility(),
    ),
    Character(
        "golem_1",
        ExactValues((4, 4, 6, 8)),
        points=2,
        copies=1,
        ability_type=AbilityType.RED,
        ability=GainActionsAbility(3),
    ),
    Character(
        "golem_2",
        ExactValues((1, 3, 5, 7)),
        points=2,
        copies=1,
        ability_type=AbilityType.RED,
        ability=GainActionsAbility(3),
    ),
    *(
        Character(
            f"barbarian_{value}",
            ExactValues((value, value)),
            points=1,
            copies=1,
            ability_type=AbilityType.BLUE,
            ability=VirtualPearlAbility((value,)),
        )
        for value in range(1, 8)
    ),
    Character(
        "rumpelstiltskin",
        ExactValues((3, 3, 3)),
        points=1,
        copies=1,
        ability_type=AbilityType.BLUE,
        ability=PearlValueSubstitutionAbility(3, (1, 2, 4, 5, 6, 7, 8)),
    ),
    Character(
        "peter_pan",
        FixedCountSum(3, 10),
        points=1,
        copies=1,
        ability_type=AbilityType.BLUE,
        ability=PearlValueSubstitutionAbility(1, (8,)),
    ),
    Character(
        "fuchur",
        ExactValues((1, 1, 1, 1)),
        points=0,
        copies=1,
        ability_type=AbilityType.BLUE,
        ability=VirtualPearlAbility(tuple(range(1, 9))),
    ),
    Character(
        "phoenix",
        ExactValues((1, 2)),
        points=0,
        copies=2,
        ability_type=AbilityType.BLUE,
        ability=VirtualPearlAbility((8,)),
    ),
)
