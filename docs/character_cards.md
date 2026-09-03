# Character Cards

This file contains the concrete character-card data used by the project.

For all game rules and requirement semantics, refer to `docs/rules.md`.

Do not invent missing card data.

---

## Green cards — no special ability

| ID | Copies | Requirement | Power Points | Diamonds |
|---|---:|---|---:|---:|
| goblins | 3 | one pair | 1 | 0 |
| fluffy | 2 | three cards of the same value | 2 | 0 |
| lion | 1 | 8, 8, 8, 8 | 5 | 0 |
| dwarf | 3 | 6, 6, 8, 8 | 3 | 0 |
| hansel_and_gretel | 2 | 8, 8 | 2 | 0 |
| frau_holle | 2 | 7, 7, 7, 7 | 4 | 0 |
| groot | 1 | four cards of the same value | 3 | 0 |
| bilbo_odd | 1 | three odd-valued cards | 1 | 1 |
| bilbo_even | 1 | three even-valued cards | 1 | 1 |
| gnome | 2 | one pair AND 6, 6 | 2 | 1 |
| captain_hook | 1 | 2, 2, 2 AND 1 diamond | 3 | 0 |
| terminator | 1 | exactly 3 cards with a total value of 20 | 2 | 0 |
| unicorn | 1 | 1, 2, 3, 4 | 1 | 2 |
| trump | 2 | 7, 7, 8, 8 | 3 | 1 |

Total cards in this section: 23

All cards in this section have no special ability.

---

## Red cards — one-time ability on activation

| ID | Copies | Requirement | Power Points | Diamonds | One-time Ability |
|---|---:|---|---:|---:|---|
| irrlicht_1 | 1 | three 3s OR three 6s | 3 | 0 | Both neighboring players may also activate this character while it is on the owner's portal and thereby gain its points instead. |
| irrlicht_2 | 1 | three 4s OR three 5s | 3 | 0 | Both neighboring players may also activate this character while it is on the owner's portal and thereby gain its points instead. |
| puss_in_boots | 1 | 3, 4, 5 | 1 | 0 | When activating this character, the player may keep one of the three pearl cards used for the activation instead of discarding it. |
| dementor | 1 | two pairs | 2 | 0 | The next player receives one additional action on their next turn. |
| golem_1 | 1 | 4, 4, 6, 8 | 2 | 0 | Immediately gain 3 additional actions. |
| golem_2 | 1 | 1, 3, 5, 7 | 2 | 0 | Immediately gain 3 additional actions. |
| tinkerbell | 2 | 5, 6, 7 | 1 | 0 | Look at another player's pearl cards and take one card of your choice. |
| medusa | 2 | exactly 3 cards with a total value of 7 | 1 | 0 | Discard one character from another player's portal. |

Total cards in this section: **10**

All cards in this section have a red one-time ability.

---

## Blue cards — persistent abilities

For blue cards, the timing of the ability is relevant:

- `before_turn`
- `during_turn`
- `after_turn`

| ID | Copies | Requirement | Power Points | Diamonds | Timing | Persistent Ability |
|---|---:|---|---:|---:|---|---|
| barbarian_1 | 1 | 1, 1 | 1 | 0 | during_turn | Provides one virtual pearl of value 1 for character activations. |
| barbarian_2 | 1 | 2, 2 | 1 | 0 | during_turn | Provides one virtual pearl of value 2 for character activations. |
| barbarian_3 | 1 | 3, 3 | 1 | 0 | during_turn | Provides one virtual pearl of value 3 for character activations. |
| barbarian_4 | 1 | 4, 4 | 1 | 0 | during_turn | Provides one virtual pearl of value 4 for character activations. |
| barbarian_5 | 1 | 5, 5 | 1 | 0 | during_turn | Provides one virtual pearl of value 5 for character activations. |
| barbarian_6 | 1 | 6, 6 | 1 | 0 | during_turn | Provides one virtual pearl of value 6 for character activations. |
| barbarian_7 | 1 | 7, 7 | 1 | 0 | during_turn | Provides one virtual pearl of value 7 for character activations. |
| rumpelstiltskin | 1 | 3, 3, 3 | 1 | 0 | during_turn | Any pearl card with value 3 may be used as any pearl value for character activation. |
| peter_pan | 1 | exactly 3 cards with a total value of 10 | 1 | 0 | during_turn | Pearl cards with value 1 may also be used as value 8 for character activation. |
| reaper | 1 | 1, 8 | 1 | 0 | after_turn | The player may discard all pearl cards in hand and draw the same number of pearl cards from the pearl draw deck. |
| little_red_riding_hood | 1 | 4, 5, 6, 7, 8 | 1 | 0 | persistent | The player receives one additional action on every turn. |
| fuchur | 1 | 1, 1, 1, 1 | 0 | 0 | during_turn | Provides one wildcard virtual pearl that may represent any pearl value for character activations. It may be used for any number of activations during the turn. |
| amazon | 1 | 3, 5, 7 | 1 | 1 | during_turn | Diamonds may modify a pearl card by either +1 or -1 instead of only +1. |
| snow_white | 1 | 2 | 0 | 1 | during_turn | A pearl card with value 2 may be converted into one diamond. |
| mad_hatter | 1 | sequence of 5 consecutive pearl values | 2 | 0 | before_turn | Before the player's turn, one character on the player's own portal may be exchanged with one face-up character from the character market. |
| dumbledore | 1 | sequence of 3 consecutive pearl values | 1 | 0 | before_turn | Before the player's turn, the player may look at the top card of the character draw deck without spending an action. |
| phoenix | 2 | 1, 2 | 0 | 0 | during_turn | Provides one virtual pearl of value 8 for character activations. |
| flying_monkey | 3 | any number of pearl cards with a total value of 10 | 1 | 0 | persistent | The player's end-of-turn pearl hand limit is increased from 5 to 6. |

Total cards in this section: **21**

All cards in this section have a blue persistent ability.