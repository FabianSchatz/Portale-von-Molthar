"""Per-seat JSON views of a running game: what each player may see and do.

Every view is built for one seat. Hands are private: a seat sees only its own
pearls (in `TableView`) and the hand sizes of the others; legal actions, activation
payment plans, and decision prompts are only included for the seat that has to move.
All keys are snake_case and mirror
``frontend/src/api/types.ts``.
"""

from typing import Final, Literal, TypeAlias, TypedDict

import pyspiel

from portale_von_molthar.agents.bots import Difficulty
from portale_von_molthar.game.cards import CHARACTERS, Character
from portale_von_molthar.game.decisions import BlueAbilityDecision, RedAbilityDecision
from portale_von_molthar.game.molthar import Action, MoltharState
from portale_von_molthar.game.payments import PaymentPlan, PearlPayment, PearlSource
from portale_von_molthar.services.catalog import character_name

MoveKind: TypeAlias = Literal[
    "take_pearl",
    "refresh_pearls",
    "take_character",
    "discard",
    "convert",
    "choice",
]
LogTone: TypeAlias = Literal["power", "danger"]

ACTIVATION_ACTIONS: Final = frozenset(
    {
        Action.ACTIVATE_0,
        Action.ACTIVATE_1,
        Action.ACTIVATE_NEIGHBOR_0,
        Action.ACTIVATE_NEIGHBOR_1,
        Action.ACTIVATE_PREVIOUS_NEIGHBOR_0,
        Action.ACTIVATE_PREVIOUS_NEIGHBOR_1,
    },
)
# Actions that use up one of the turn's actions, numbered in the log.
TURN_ACTIONS: Final = frozenset(range(Action.ACTIVATE_1 + 1)) | ACTIVATION_ACTIONS
_CHARACTERS_BY_ID: Final = {character.id: character for character in CHARACTERS}
_CHARACTER_DECK_SOURCE: Final = 2
_SIMPLE_CHOICES: Final = {
    "KeepNoPearl": ("Keep no pearl", "kept no pearl"),
    "ReaperKeepHand": ("Keep your hand", "kept their hand"),
    "ReaperRedrawHand": ("Redraw your hand", "redrew their hand"),
    "MadHatterSkip": ("Don't swap", "kept their portal"),
}
_PAST_TENSE: Final = {
    "activate": "activated",
    "choose": "chose",
    "discard": "discarded",
    "keep": "kept",
    "replace": "replaced",
    "swap": "swapped",
    "take": "took",
    "turn": "turned",
}


class PlayerView(TypedDict):
    """Public information about one seat; its hand only as a count.

    Attributes:
        bot: Difficulty of a bot seat, ``None`` for a human player.
    """

    seat: int
    name: str
    connected: bool
    bot: Difficulty | None
    points: int
    diamonds: int
    hand_size: int
    hand_limit: int
    portal: list[str]
    activated: list[str]


class MoveView(TypedDict):
    """One legal action of the viewing seat that is not an activation.

    Attributes:
        action: OpenSpiel action id to send back.
        kind: What the action does; decides where the frontend offers it.
        text: Button text in sentence case, such as ``"Take pearl 5"``.
        slot: Display slot for takes (``None`` is the hidden deck card).
        replace: Portal slot discarded to make room for a new character.
    """

    action: int
    kind: MoveKind
    text: str
    slot: int | None
    replace: int | None


class PlanView(TypedDict):
    """One complete way to pay for an activation.

    Attributes:
        index: Index to send back with the ``activate`` command.
        cards: Printed values of the hand pearls discarded by this plan.
        labels: One label per pearl position, such as ``"3 as 4 (diamond)"``.
        diamonds: Diamonds spent, both printed in the requirement and as modifiers.
    """

    index: int
    cards: list[int]
    labels: list[str]
    diamonds: int


class ActivationView(TypedDict):
    """A character the viewing seat can activate now, with every way to pay."""

    action: int
    owner: int
    slot: int
    character: str
    plans: list[PlanView]


class PromptView(TypedDict):
    """The decision the viewing seat has to make now.

    Attributes:
        kind: ``"turn"`` for a normal action, ``"discard"`` at the hand limit, or a
            red (`RedChoice`) or blue (`BlueChoice`) ability choice.
        count: Pearls to discard for ``"discard"``, else 0.
        target: Opponent addressed by a red ability, if already chosen.
    """

    kind: str
    count: int
    target: int | None


class TableView(TypedDict):
    """The game table as seen by one seat."""

    hand: list[int]
    pearl_display: list[int]
    pearl_deck: int
    pearl_discard: int
    character_display: list[str]
    character_deck: int
    character_discard: int
    current_player: int | None
    actions_left: int
    final_turns: int | None
    peeked: str | None
    prompt: PromptView | None
    moves: list[MoveView]
    activations: list[ActivationView]


class LogEntry(TypedDict):
    """One line of the Chronicle.

    Attributes:
        player: Name of the acting player.
        text: Past tense with a lowercase verb, such as ``"took pearl 5"``.
        highlight: Changed amount set in ink after the text, such as ``"+3"``.
        tone: ``"power"`` paints the highlight gold, ``"danger"`` the line oxblood.
        action: Number of the turn action, ``None`` for free moves and choices.
    """

    player: str
    text: str
    highlight: str | None
    tone: LogTone | None
    action: int | None


def player_views(
    state: MoltharState | None,
    names: list[str],
    connected: list[bool],
    bots: list[Difficulty | None],
) -> list[PlayerView]:
    """Return the public information of every seat.

    Args:
        state: Running game, or ``None`` in the lobby (all counters are zero).
        names: Player name per seat.
        connected: Whether each seat currently has an open connection.
        bots: Difficulty of each bot seat, ``None`` for human seats.

    Returns:
        One view per seat, in seat order.
    """
    if state is None:
        return [
            PlayerView(
                seat=seat,
                name=name,
                connected=connected[seat],
                bot=bots[seat],
                points=0,
                diamonds=0,
                hand_size=0,
                hand_limit=5,
                portal=[],
                activated=[],
            )
            for seat, name in enumerate(names)
        ]
    hands, limits, portals = state.hands, state.hand_limits, state.portals
    activated = state.activated_characters
    return [
        PlayerView(
            seat=seat,
            name=name,
            connected=connected[seat],
            bot=bots[seat],
            points=state.scores[seat],
            diamonds=state.diamonds[seat],
            hand_size=len(hands[seat]),
            hand_limit=limits[seat],
            portal=portals[seat],
            activated=activated[seat],
        )
        for seat, name in enumerate(names)
    ]


def table_view(state: MoltharState, seat: int, names: list[str]) -> TableView:
    """Return the table as seen by `seat`, with its options when it is to move.

    Args:
        state: Running or finished game, never at a chance node.
        seat: Viewing player.
        names: Player name per seat, used in move texts.

    Returns:
        The view; `prompt`, `moves`, and `activations` are empty unless `seat` moves.
    """
    mover = state.current_player()
    moving = mover == seat
    legal = state.legal_actions(seat) if moving else []
    peeked = state.peeked_character
    return TableView(
        hand=state.hands[seat],
        pearl_display=state.pearl_display,
        pearl_deck=state.pearl_deck_size,
        pearl_discard=state.pearl_discard_size,
        character_display=state.character_display,
        character_deck=state.character_deck_size,
        character_discard=state.character_discard_size,
        current_player=None if mover == pyspiel.PlayerId.TERMINAL else mover,
        actions_left=state.actions_left,
        final_turns=state.final_turns,
        peeked=peeked[1] if peeked is not None and peeked[0] == seat else None,
        prompt=_prompt(state, seat) if moving else None,
        moves=[
            _move_view(state, seat, action, names)
            for action in legal
            if action not in ACTIVATION_ACTIONS
        ],
        activations=[
            _activation_view(state, seat, action)
            for action in legal
            if action in ACTIVATION_ACTIONS
        ],
    )


def activation_target(state: MoltharState, player: int, action: int) -> tuple[int, int]:
    """Return the ``(portal owner, portal slot)`` an activation action addresses.

    Args:
        state: Current game.
        player: Player activating.
        action: One of `ACTIVATION_ACTIONS`.

    Returns:
        The owner of the portal holding the character and its slot there.
    """
    players = state.num_players()
    if action <= Action.ACTIVATE_1:
        return player, action - Action.ACTIVATE_0
    if action <= Action.ACTIVATE_NEIGHBOR_1:
        return (player + 1) % players, action - Action.ACTIVATE_NEIGHBOR_0
    return (player - 1) % players, action - Action.ACTIVATE_PREVIOUS_NEIGHBOR_0


def activation_character(state: MoltharState, player: int, action: int) -> Character:
    """Return the character an activation action addresses."""
    owner, slot = activation_target(state, player, action)
    return _CHARACTERS_BY_ID[state.portals[owner][slot]]


def activation_plans(state: MoltharState, player: int, action: int) -> tuple[PaymentPlan, ...]:
    """Return every complete payment plan for an activation, in the engine's order.

    The indices of this tuple are the plan indices of `ActivationView`; the engine's
    payment decision narrows down exactly these plans.

    Args:
        state: Current game.
        player: Player activating.
        action: One of `ACTIVATION_ACTIONS`.

    Returns:
        The engine's complete, non-dominated plans.
    """
    character = activation_character(state, player, action)
    return state._activation_plans(player, character)  # noqa: SLF001  # engine planner


def describe_action(
    state: MoltharState,
    player: int,
    action: int,
    names: list[str],
) -> tuple[str, str]:
    """Return the button text and the log text of a legal player action.

    Args:
        state: Game before the action is applied.
        player: Player taking the action.
        action: Legal action id.
        names: Player name per seat.

    Returns:
        ``(text, log)``, such as ``("Take pearl 5", "took pearl 5")``.
    """
    if action in TURN_ACTIONS:
        return _pair(*_turn_phrase(state, player, action))
    label = state.action_to_string(player, action)
    if label in _SIMPLE_CHOICES:
        return _SIMPLE_CHOICES[label]
    head, _, rest = label.partition(":")
    step = state.pending_step
    target = step.target_player if isinstance(step, RedAbilityDecision) else None
    if head == "StealPearl" and target is not None:
        texts = _pair("take", f"pearl {rest} from {names[target]}")
    elif head == "DiscardPortal" and target is not None:
        victim = character_name(state.portals[target][int(rest)])
        texts = _pair("discard", f"{victim} from {names[target]}'s portal")
    elif head == "TargetPlayer":
        texts = _pair("choose", names[int(rest)])
    elif head == "MadHatterSwap":
        old, new = rest.split("<->")
        texts = _pair("swap", f"{character_name(old)} for {character_name(new)}")
    elif head == "ConvertToDiamond":
        texts = _pair("turn", f"a {rest.split(':')[0]} into a diamond")
    else:
        texts = _pair({"Discard": "discard", "KeepPearl": "keep"}[head], f"pearl {rest}")
    return texts


def _pair(verb: str, subject: str) -> tuple[str, str]:
    """Return the imperative button text and the past-tense log text."""
    return f"{verb.capitalize()} {subject}", f"{_PAST_TENSE[verb]} {subject}"


def _turn_phrase(state: MoltharState, player: int, action: int) -> tuple[str, str]:
    """Return ``(verb, subject)`` of a turn action, such as ``("take", "pearl 5")``."""
    display = state.character_display
    if action <= Action.TAKE_PEARL_3:
        phrase = ("take", f"pearl {state.pearl_display[action]}")
    elif action == Action.TAKE_PEARL_DECK:
        phrase = ("take", "a hidden pearl")
    elif action == Action.REFRESH_PEARLS:
        phrase = ("replace", "the pearl display")
    elif action <= Action.TAKE_CHARACTER_1:
        phrase = ("take", character_name(display[action - Action.TAKE_CHARACTER_0]))
    elif action == Action.TAKE_CHARACTER_DECK:
        phrase = ("take", "a hidden character")
    elif action <= Action.REPLACE_PORTAL_1_DECK:
        portal_slot, source = divmod(action - Action.REPLACE_PORTAL_0_0, 3)
        old = character_name(state.portals[player][portal_slot])
        new = (
            "a hidden character"
            if source == _CHARACTER_DECK_SOURCE
            else character_name(display[source])
        )
        phrase = ("replace", f"{old} with {new}")
    else:
        phrase = ("activate", character_name(activation_character(state, player, action).id))
    return phrase


def _move_view(state: MoltharState, player: int, action: int, names: list[str]) -> MoveView:
    """Return a legal non-activation action with its kind and slots."""
    kind: MoveKind = "choice"
    slot: int | None = None
    replace: int | None = None
    if action <= Action.TAKE_PEARL_DECK:
        kind = "take_pearl"
        slot = None if action == Action.TAKE_PEARL_DECK else action
    elif action == Action.REFRESH_PEARLS:
        kind = "refresh_pearls"
    elif action <= Action.TAKE_CHARACTER_DECK:
        kind = "take_character"
        source = action - Action.TAKE_CHARACTER_0
        slot = None if source == _CHARACTER_DECK_SOURCE else source
    elif action <= Action.REPLACE_PORTAL_1_DECK:
        kind = "take_character"
        replace, source = divmod(action - Action.REPLACE_PORTAL_0_0, 3)
        slot = None if source == _CHARACTER_DECK_SOURCE else source
    elif Action.DISCARD_1 <= action <= Action.DISCARD_8:
        kind = "discard"
    elif action == Action.CONVERT_2_TO_DIAMOND_SNOW_WHITE:
        kind = "convert"
    text, _ = describe_action(state, player, action, names)
    return MoveView(action=action, kind=kind, text=text, slot=slot, replace=replace)


def _activation_view(state: MoltharState, player: int, action: int) -> ActivationView:
    """Return an activatable character with every way to pay for it."""
    owner, slot = activation_target(state, player, action)
    return ActivationView(
        action=action,
        owner=owner,
        slot=slot,
        character=state.portals[owner][slot],
        plans=[
            _plan_view(index, plan)
            for index, plan in enumerate(activation_plans(state, player, action))
        ],
    )


def _plan_view(index: int, plan: PaymentPlan) -> PlanView:
    """Return the discarded cards and readable labels of one payment plan."""
    labels = [_payment_text(pearl) for pearl in plan.pearls]
    if plan.required_diamonds:
        plural = "s" if plan.required_diamonds > 1 else ""
        labels.append(f"{plan.required_diamonds} diamond{plural}")
    return PlanView(
        index=index,
        cards=sorted(plan.discarded_values),
        labels=labels,
        diamonds=plan.diamonds_spent,
    )


def _payment_text(pearl: PearlPayment) -> str:
    """Return a label for one pearl position, such as ``"3 as 4 (diamond)"``."""
    if pearl.source is PearlSource.VIRTUAL:
        return f"{character_name(pearl.source_id or '')} as {pearl.effective_value}"
    reasons = [character_name(modifier) for modifier in pearl.modifiers]
    if pearl.diamonds_spent:
        reasons.append("diamond")
    if not reasons:
        return str(pearl.printed_value)
    return f"{pearl.printed_value} as {pearl.effective_value} ({', '.join(reasons)})"


def _prompt(state: MoltharState, seat: int) -> PromptView:
    """Return the decision `seat` has to make; `seat` is the player to move."""
    step = state.pending_step
    kind = "turn"
    count = 0
    target: int | None = None
    if isinstance(step, RedAbilityDecision):
        kind = step.choice.value
        target = step.target_player
    elif isinstance(step, BlueAbilityDecision):
        kind = step.choice.value
    elif not state.actions_left:
        kind = "discard"
        count = len(state.hands[seat]) - state.hand_limits[seat]
    return PromptView(kind=kind, count=count, target=target)
