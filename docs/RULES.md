# Die Portale von Molthar — Base Game Rules

This document describes the rules of the base game **Die Portale von Molthar** in a form intended for implementing the game in code.

Treat this file as the authoritative rules reference for the project.

Do not search the internet for missing rules and do not invent rules. If something required for an implementation is not specified here or in the project's card data, stop and point out the missing information.

This document describes the real game rules. The current implementation may intentionally support only a subset of them.

---

## 1. Players

The game supports **2 to 5 players**.

Players take turns clockwise.

One player is the start player.

---

## 2. Components

The base game contains:

* 56 pearl cards
* pearl values range from 1 to 8
* each pearl value occurs 7 times
* 54 character cards
* 5 player portals

Pearl cards and character cards use separate:

* draw decks
* discard piles

If a draw deck becomes empty, shuffle its corresponding discard pile and use it as the new draw deck.

---

## 3. Public and private information

The following information is public:

* the four face-up pearl cards
* the two face-up character cards
* characters on player portals
* activated characters
* diamonds owned by players
* power points
* number of cards in each player's hand

A player's pearl cards in hand are private.

Cards in draw decks are hidden.

---

## 4. Setup

Shuffle the pearl deck and character deck separately.

Create the pearl market by revealing:

* 4 pearl cards

Create the character market by revealing:

* 2 character cards

Each player starts with:

* an empty pearl-card hand
* an empty portal
* no activated characters
* no diamonds
* 0 power points

The chosen start player takes the first turn.

Special swap symbols on pearl cards do not trigger during setup.

---

## 5. Player turn

A normal turn consists of exactly **3 actions**.

For every action, the active player chooses one of the following four action types:

1. Take a pearl card
2. Replace the pearl market
3. Put a character on the player's portal
4. Activate a character

Actions may be performed:

* in any order
* more than once during the same turn

Unless a special ability modifies the number of actions, the player receives 3 actions.

Executing a red or blue character ability is not itself an action.

---

# 6. Actions

## 6.1 Take a pearl card

The player chooses either:

* one of the four face-up pearl cards, or
* the top hidden card of the pearl draw deck

and adds it to their hand.

### Taking a face-up pearl

If a face-up pearl is taken:

1. Remove it from the pearl market.
2. Add it to the active player's hand.
3. Immediately reveal the top card of the pearl deck into the empty market position.

If the newly revealed pearl card has a character-swap symbol, immediately:

1. discard both face-up character cards,
2. reveal two new character cards.

The swap symbol does not trigger during initial setup.

### Taking a hidden pearl

If the player chooses the top card of the pearl draw deck:

* add it directly to the player's hand
* the pearl market does not change

A swap symbol on a pearl drawn directly into a player's hand does not trigger.

---

## 6.2 Replace the pearl market

Discard all four face-up pearl cards.

Then reveal four new pearl cards from the pearl draw deck.

This costs one action.

---

## 6.3 Put a character on the portal

The player chooses either:

* one of the two face-up character cards, or
* the top hidden card of the character draw deck

and puts that character on their portal.

If a face-up character is taken, immediately replace it with the top card of the character draw deck.

A portal can contain at most **2 character cards**.

If both portal spaces are occupied and the player wants to take another character:

1. the player must first choose one character currently on their portal,
2. discard that character,
3. place the new character on the portal.

A character on the portal is not yet activated and does not provide its power points, diamonds, or abilities.

---

## 6.4 Activate a character

Only a character currently available for activation may be activated.

Normally this means a character on the active player's own portal.

The player must satisfy the activation requirement printed on the character card.

Required pearl cards are played from the player's hand and placed on the pearl discard pile.

After paying the requirement:

1. remove the character from the portal,
2. mark it as activated,
3. place it in the player's activated-character area,
4. apply its printed rewards and abilities.

Activation costs one action.

---

# 7. Activation requirements

Character cards may use several different kinds of pearl requirements.

The implementation must model the requirement itself rather than treating every requirement as a simple tuple of exact values.

## 7.1 Exact pearl values

Example:

`1, 1`

requires exactly two pearl cards with value 1.

Example:

`5, 6, 7`

requires one 5, one 6 and one 7.

Repeated values require multiple separate cards.

---

## 7.2 N of a kind

A requirement may ask for pearl cards with equal values.

Possible examples include:

* a pair
* three of a kind
* four of a kind

The actual value may be unrestricted unless the card explicitly specifies it.

---

## 7.3 Multiple pairs

A requirement may ask for multiple pairs.

For example:

* two arbitrary pairs

Each pair consists of two pearl cards with the same value.

---

## 7.4 Even values

A requirement may ask for a given number of pearl cards whose values are even.

Valid pearl values are:

* 2
* 4
* 6
* 8

Example:

three even cards

does not require the cards to have different values unless explicitly specified.

---

## 7.5 Odd values

A requirement may ask for a given number of pearl cards whose values are odd.

Valid pearl values are:

* 1
* 3
* 5
* 7

Example:

three odd cards

does not require the cards to have different values unless explicitly specified.

---

## 7.6 Exact sum with a fixed number of cards

A requirement may specify both:

* the number of pearl cards
* their required total value

Example:

three cards whose values sum to 7.

Exactly three pearl cards must be used.

---

## 7.7 Exact sum with a variable number of cards

A requirement may specify a required total without fixing the number of cards.

Example:

any number of pearl cards whose values sum to 10.

The chosen cards must sum exactly to the target.

---

## 7.8 Consecutive values

A requirement may ask for a consecutive sequence.

Examples include sequences of:

* 3 cards
* 5 cards

Every next card must have a value exactly one greater than the previous card.

Examples of valid length-3 sequences:

* 1, 2, 3
* 3, 4, 5
* 6, 7, 8

Values do not wrap from 8 back to 1.

---

## 7.9 Alternatives

Some requirements allow one of several alternatives.

Example:

* three 4-value pearls
* OR three 5-value pearls

Only one complete alternative needs to be satisfied.

---

## 7.10 Combined requirements

A character may combine multiple requirements.

Example:

* one arbitrary pair
* AND a pair of 6-value pearls

All parts of the requirement must be satisfied using the required cards.

A physical pearl card cannot satisfy two different consumed positions of the same activation requirement simultaneously.

---

# 8. Diamonds

Activated characters may award diamonds.

For every diamond symbol awarded by an activated character:

1. take one character card from the character draw deck,
2. place it face down with its diamond side visible in the player's diamond area.

That card now represents a diamond rather than a playable character.

---

## 8.1 Using a diamond for activation

A diamond can modify one pearl card used to activate a character.

In the base game, one diamond may increase the value of one pearl card by exactly 1.

Example:

* pearl value 3 + one diamond = value 4

Restrictions:

* at most one diamond may modify a particular pearl card
* a pearl value may not be increased to 9

A diamond used this way is discarded onto the character discard pile.

Unless a special character ability says otherwise, diamonds cannot decrease pearl values.

---

## 8.2 Diamonds inside requirements

Some character requirements may explicitly require a diamond in addition to pearl cards.

If a requirement explicitly contains a diamond, that diamond must also be paid.

---

# 9. Character rewards

An activated character can provide:

* power points
* diamonds
* a special ability
* a combination of these

Power points are provided by activated characters.

Characters still sitting on a portal do not provide their power points.

---

# 10. Special abilities

Character abilities are divided into two types.

## 10.1 Red abilities

Red abilities:

* are one-time effects
* must be resolved immediately after the character is activated
* do not cost an action

## 10.2 Blue abilities

Blue abilities:

* become active after the character is activated
* are persistent
* do not themselves cost an action
* may have specific timing restrictions printed by their ability

Examples of possible timing include:

* before the player's first action
* during the player's turn
* after the player's final action

The concrete behavior of each special character ability belongs in the character-card data and is not defined by this general rules document.

---

# 11. Pearl values provided by activated characters

Some activated characters provide an additional virtual pearl value.

This may be:

* a specific value such as 5
* a wildcard `?`

A wildcard may represent any pearl value from 1 through 8.

Such a virtual pearl:

* may be used once during each character activation
* reduces the number of physical pearl cards that must be played
* is not a hand card
* is not discarded after use
* cannot itself be modified by a diamond

Multiple activated characters may contribute virtual pearls to the same activation if their abilities permit it.

---

# 12. End of turn

After the active player has performed their final action, their turn ends.

The normal pearl hand limit is **5 cards**.

A player may temporarily hold more than five pearl cards during their turn.

At the end of the turn, if the player has more cards than their current hand limit, they must discard cards of their choice until the limit is satisfied.

Then the next player clockwise becomes the active player.

Some character abilities can modify the hand limit or number of actions.

---

# 13. End of game

When a player reaches **12 or more power points** from activated characters, the end of the game is triggered.

Do not end the game immediately.

First:

1. finish the current round through the player immediately before the start player,
2. then every player receives exactly one additional turn,
3. after those final turns, the game ends.

The player with the most power points wins.

If multiple players have the same highest number of power points, the tied player with more diamonds wins.

If both power points and diamond counts are still equal, this rules document defines no additional tiebreaker.

---

# 14. Implementation notes

These are implementation constraints derived from the rules, not additional game rules.

## Game state should eventually track

Global state:

* current player
* remaining actions
* start player
* pearl draw deck
* pearl discard pile
* pearl market
* character draw deck
* character discard pile
* character market
* whether the end-game sequence has been triggered
* remaining final turns

Per-player state:

* pearl hand
* characters on portal
* activated characters
* diamonds
* effective hand limit
* effective actions per turn

## Randomness

Shuffling and hidden draws are random game events.

Because the OpenSpiel game declares `EXPLICIT_STOCHASTIC`, randomness should eventually be represented through OpenSpiel chance nodes rather than hidden calls to Python's `random` module.

This can be implemented incrementally.

---

# 15. Card-data boundary

This document defines the rules and the meaning of card symbols.

It does **not** define the complete contents of all 54 character cards.

Concrete character-card data should live separately, for example in:

`docs/character_cards.md`

or directly in a structured data module.

Each character definition should eventually specify at least:

* stable identifier
* name, if needed
* activation requirement
* power points
* diamonds awarded
* ability type: none / red / blue
* concrete special ability, if present

Do not fabricate missing character-card data.

The same applies to pearl cards with special printed symbols: the rules explain what a symbol does, while the exact deck composition belongs in card data.