"""Display data for every character card, derived from `cards.CHARACTERS`.

The frontend renders cards from this catalog, so the engine's card data stays the
single source of truth for names, requirements, rewards, and ability text.
"""

import re
from functools import cache
from typing import Final, Literal, TypeAlias, TypedDict

from portale_von_molthar.game.abilities import (
    AbilityTiming,
    AbilityType,
    CharacterAbility,
    DiamondDecreaseAbility,
    DiscardPortalAbility,
    GainActionsAbility,
    HandLimitAbility,
    KeepPearlAbility,
    NeighborActivationAbility,
    NextPlayerActionAbility,
    PearlToDiamondAbility,
    PearlValueSubstitutionAbility,
    PeekCharacterDeckAbility,
    PortalMarketSwapAbility,
    RedrawHandAbility,
    StealPearlAbility,
    TurnActionsAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.game.cards import CHARACTERS, Character
from portale_von_molthar.game.requirements import (
    AllOf,
    AnyOf,
    ConsecutiveValues,
    ExactValues,
    FixedCountSum,
    ParityValues,
    Requirement,
    SameValue,
    VariableCountSum,
)

# Exact values render as pearl tiles; 'or', 'and', and 'diamond' are separators and a paid diamond.
RequirementView: TypeAlias = str | list[int | str]
CardKind: TypeAlias = Literal["green", "red", "blue"]

_KINDS: Final[dict[AbilityType, CardKind]] = {
    AbilityType.NONE: "green",
    AbilityType.RED: "red",
    AbilityType.BLUE: "blue",
}
_ID_SUFFIX: Final = re.compile(r"_(\d+|odd|even)$")
_LOWERCASE_WORDS: Final = frozenset({"and", "in"})
_SAME_VALUE_WORDS: Final = {2: "One pair", 3: "Three of a kind", 4: "Four of a kind"}
_ALL_PEARL_VALUES: Final = frozenset(range(1, 9))
# Blue abilities whose dataclass carries no explicit timing (see docs/character_cards.md).
_FIXED_TIMINGS: Final[dict[type, AbilityTiming]] = {
    RedrawHandAbility: AbilityTiming.AFTER_TURN,
    PortalMarketSwapAbility: AbilityTiming.BEFORE_TURN,
    PeekCharacterDeckAbility: AbilityTiming.BEFORE_TURN,
    TurnActionsAbility: AbilityTiming.PERSISTENT,
    HandLimitAbility: AbilityTiming.PERSISTENT,
    DiamondDecreaseAbility: AbilityTiming.DURING_TURN,
    PearlToDiamondAbility: AbilityTiming.DURING_TURN,
}
_FIXED_TEXTS: Final[dict[type, str]] = {
    NeighborActivationAbility: "Your neighbours may activate it too.",
    KeepPearlAbility: "Keep one of the pearls you paid.",
    NextPlayerActionAbility: "The next player gets 1 extra action.",
    StealPearlAbility: "Look at a hand and take one pearl.",
    DiscardPortalAbility: "Discard a character from another portal.",
    DiamondDecreaseAbility: "Diamonds may also lower a pearl by 1.",
    RedrawHandAbility: "You may redraw your whole hand.",
    PortalMarketSwapAbility: "Swap a portal character with a face-up one.",
    PeekCharacterDeckAbility: "Look at the top card of the character deck.",
}


class CharacterInfo(TypedDict):
    """What the frontend needs to draw one character card.

    Attributes:
        id: Stable identifier from `cards.CHARACTERS`.
        name: Display name; copies such as ``irrlicht_1`` and ``irrlicht_2`` share it.
        kind: Ability colour: green (none), red (one-time), blue (persistent).
        requirement: Pearl tiles or a short sentence, see `RequirementView`.
        points: Power points awarded on activation.
        diamonds: Diamonds awarded on activation.
        ability: One short sentence for the card's back, ``None`` for green cards.
        timing: When a blue ability applies, ``None`` for green and red cards.
    """

    id: str
    name: str
    kind: CardKind
    requirement: RequirementView
    points: int
    diamonds: int
    ability: str | None
    timing: str | None


@cache
def character_catalog() -> dict[str, CharacterInfo]:
    """Return display data for every character, keyed by character id.

    Returns:
        One entry per distinct character card of the base game.
    """
    return {character.id: _character_info(character) for character in CHARACTERS}


def character_name(card_id: str) -> str:
    """Return the display name of a character id, such as ``"Irrlicht"`` for ``irrlicht_1``.

    Args:
        card_id: Stable identifier from `cards.CHARACTERS`.

    Returns:
        The title-cased name without a copy or variant suffix.
    """
    words = _ID_SUFFIX.sub("", card_id).split("_")
    return " ".join(
        word if index and word in _LOWERCASE_WORDS else word.capitalize()
        for index, word in enumerate(words)
    )


def _character_info(character: Character) -> CharacterInfo:
    """Return the display data of one character."""
    return CharacterInfo(
        id=character.id,
        name=character_name(character.id),
        kind=_KINDS[character.ability_type],
        requirement=_requirement_view(character.requirement, character.diamonds_cost),
        points=character.points,
        diamonds=character.diamonds,
        ability=None if character.ability is None else _ability_text(character.ability),
        timing=_ability_timing(character),
    )


def _requirement_view(requirement: Requirement, diamonds_cost: int) -> RequirementView:
    """Return pearl tiles when the requirement only names exact values, else a sentence."""
    tiles = _requirement_tiles(requirement)
    if tiles is not None:
        return [*tiles, "and", *(["diamond"] * diamonds_cost)] if diamonds_cost else tiles
    text = _requirement_text(requirement)
    return f"{text} + {diamonds_cost} diamond" if diamonds_cost else text


def _requirement_tiles(requirement: Requirement) -> list[int | str] | None:
    """Return exact values joined by 'or'/'and', or ``None`` for other requirements."""
    if isinstance(requirement, ExactValues):
        return list(requirement.values)
    if isinstance(requirement, (AnyOf, AllOf)):
        parts = requirement.alternatives if isinstance(requirement, AnyOf) else requirement.parts
        separator = "or" if isinstance(requirement, AnyOf) else "and"
        tiles: list[int | str] = []
        for part in parts:
            part_tiles = _requirement_tiles(part)
            if part_tiles is None:
                return None
            tiles.extend([separator, *part_tiles] if tiles else part_tiles)
        return tiles
    return None


def _requirement_text(requirement: Requirement) -> str:
    """Return a short sentence describing any requirement."""
    if isinstance(requirement, ExactValues):
        text = ", ".join(str(value) for value in requirement.values)
    elif isinstance(requirement, SameValue):
        text = _SAME_VALUE_WORDS.get(requirement.count, f"{requirement.count} of a kind")
    elif isinstance(requirement, ParityValues):
        text = f"{requirement.count} {requirement.parity.value} cards"
    elif isinstance(requirement, FixedCountSum):
        text = f"{requirement.count} cards totalling {requirement.total}"
    elif isinstance(requirement, VariableCountSum):
        text = f"Any cards totalling {requirement.total}"
    elif isinstance(requirement, ConsecutiveValues):
        text = f"Run of {requirement.count}"
    elif isinstance(requirement, AnyOf):
        text = " or ".join(_requirement_text(part) for part in requirement.alternatives)
    elif all(part == SameValue(2) for part in requirement.parts):
        text = "Two pairs" if len(requirement.parts) == 2 else f"{len(requirement.parts)} pairs"
    else:
        text = " + ".join(_requirement_text(part) for part in requirement.parts)
    return text


def _ability_text(ability: CharacterAbility) -> str:
    """Return one short sentence (about 45 characters) describing `ability`."""
    if type(ability) in _FIXED_TEXTS:
        return _FIXED_TEXTS[type(ability)]
    if isinstance(ability, (GainActionsAbility, TurnActionsAbility)):
        plural = "s" if ability.actions > 1 else ""
        when = "now" if isinstance(ability, GainActionsAbility) else "now and every turn"
        text = f"Gain {ability.actions} extra action{plural} {when}."
    elif isinstance(ability, VirtualPearlAbility):
        if frozenset(ability.values) == _ALL_PEARL_VALUES:
            text = "A wildcard pearl for every activation."
        else:
            values = " or ".join(str(value) for value in ability.values)
            text = f"A virtual {values} for every activation."
    elif isinstance(ability, PearlValueSubstitutionAbility):
        if frozenset(ability.effective_values) | {ability.printed_value} == _ALL_PEARL_VALUES:
            text = f"Any {ability.printed_value} counts as any value."
        else:
            values = " or ".join(str(value) for value in ability.effective_values)
            text = f"Any {ability.printed_value} may count as {values}."
    elif isinstance(ability, HandLimitAbility):
        text = f"Hand limit raised by {ability.bonus}."
    elif isinstance(ability, PearlToDiamondAbility):
        text = f"Turn any {ability.printed_value} in hand into a diamond."
    else:
        message = f"no text for ability {type(ability).__name__}"
        raise TypeError(message)
    return text


def _ability_timing(character: Character) -> str | None:
    """Return when a blue ability applies, or ``None`` for green and red cards."""
    ability = character.ability
    if character.ability_type is not AbilityType.BLUE or ability is None:
        return None
    if isinstance(ability, (VirtualPearlAbility, PearlValueSubstitutionAbility)):
        return ability.timing.value
    return _FIXED_TIMINGS[type(ability)].value
