# Canasta Rules And GUI Guide

This project implements a two-player Canasta variant with a GTK4 GUI and CLI.
This guide focuses on how to play the current implementation and how to use the GUI.

## Launching The GUI

From the project directory:

```bash
uv run canasta-gui
```

By default the GUI starts with:

- North as the `random` bot
- South as the `human` player

You can also start with explicit seat choices:

```bash
uv run canasta-gui --north human --south greedy
uv run canasta-gui --north aggro --south planner --bot-seed 7
```

The GUI looks for card images in the XDG data directory for `canasta`:

```bash
ln -sfn /path/to/ccacards/data "$HOME/.local/share/canasta"
```

You can override the asset directory directly:

```bash
uv run canasta-gui --assets-dir /path/to/card-images
```

## GUI Layout

![Main game window](docs/screenshots/main-window.png)

The window is divided into a few main areas:

- Top summary area:
  - Current round
  - Current player
  - Winner state
  - Selected card indexes
  - Whether the discard pile is frozen
  - Whether the current player has already drawn this turn
  - Round and total scores for north and south
- Stock and discard area:
  - Stock count and card back
  - Discard count and top discard card
- Controls row:
  - `Draw`
  - `Pickup Selected`
  - `Meld Selected`
  - `Add To Meld`
  - `Discard Selected`
  - `Next Round`
  - Meld selector dropdown
  - `New Game…`
- Current hand:
  - Displayed as a fanned horizontal stack
  - Click cards to select or deselect them
  - Selected cards lift upward visually
- Melds area:
  - North and south melds are shown separately
  - Red threes are shown in their own row

![Fanned hand layout](docs/screenshots/fanned-hand.png)

## Starting A New Game

![New game dialog](docs/screenshots/new-game-dialog.png)

Use `New Game…` to open a setup dialog.

From there you can choose:

- North seat: `human`, `random`, `greedy`, `safe`, `aggro`, `planner`
- South seat: `human`, `random`, `greedy`, `safe`, `aggro`, `planner`
- Bot seed: deterministic seed for bot behavior

Press `Start` to reset the game with those settings.

## Turn Flow In The GUI

Each turn follows this basic sequence:

1. Draw from stock or pick up the discard pile.
2. Optionally create new melds.
3. Optionally add cards to existing melds.
4. Discard exactly one card to end the turn.

The GUI enables and disables controls depending on what is legal at that point in the turn.

## How To Use Each Button

### Draw

- Draws 2 cards from the stock.
- You may only draw once per turn.
- Red threes drawn from the stock are auto-melded immediately.

### Pickup Selected

- Select the hand cards you want to combine with the top discard.
- Press `Pickup Selected` to take the discard pile.
- If legal, the selected cards plus the top discard form a meld.
- The rest of the discard pile goes into your hand.

### Meld Selected

- Select cards from your hand.
- Press `Meld Selected` to create a new meld.
- A meld must contain at least 3 cards.
- A meld must contain at least 1 natural card.
- Within a single meld, all natural cards must be the same rank.
- Wild cards cannot outnumber natural cards.

### Add To Meld

![Adding cards to a meld](docs/screenshots/add-to-meld.png)

- Select cards from your hand.
- If the selected cards are natural cards of one rank, the GUI automatically chooses the matching meld.
- If any selected card is wild, use the dropdown to choose the destination meld first.
- Press `Add To Meld`.

### Discard Selected

- Select exactly one card.
- Press `Discard Selected` to end your turn.
- Red threes cannot be discarded.

### Next Round

- Enabled only after a player goes out and the round is finished.
- Banks the round score and starts the next round.

## Core Rules In This Implementation

## Objective

Score points by building melds and going out. Scores accumulate across rounds.

## Deck

- Double deck
- Standard suits: spades, hearts, diamonds, clubs
- Includes jokers

## Card Values

- Joker: 50
- 2: 20
- Ace: 20
- K, Q, J, T, 9, 8: 10
- 7, 6, 5, 4, 3: 5

These values are used for meld scoring, opening-meld thresholds, and hand penalties.

## Wild Cards

Wild cards are:

- `2`
- `JOKER`

Rules for wild cards:

- A meld cannot be all wild cards.
- Wild cards cannot outnumber natural cards in a meld.

## Red Threes

Red threes are:

- `3H`
- `3D`

Behavior in this implementation:

- Red threes are auto-melded when drawn.
- They score separately.
- They cannot be discarded.

## Black Threes And Frozen Discard

Black threes are:

- `3S`
- `3C`

The discard pile becomes frozen if it contains:

- Any wild card, or
- Any black three

When the discard pile is frozen:

- You cannot pick it up with a wild card or black three on top.
- You must use exactly 2 natural hand cards matching the top discard rank.

## Opening Meld Requirement

A side's first meld(s) of the round must total at least 50 points using natural cards only.

This implementation now allows split opening melds across multiple ranks in one action, provided each rank forms its own valid meld. Example:

- `6S 6H 6D 6C QS QH QD`

This is treated as two melds in a single opening play.

If a split opening selection includes wild cards, it is rejected in one action because the target assignment of the wild cards would be ambiguous.

## Going Out

A round ends when a player empties their hand by making legal plays and discarding appropriately.

At round end:

- Melded cards score positively
- Canastas receive a bonus
- Cards left in hand count as penalties
- Red threes score according to the current rules implementation

## Scoring Notes

This implementation includes:

- Round score calculation
- Total score accumulation across rounds
- Hand penalties at round end
- Canasta bonus for melds with 7 or more cards

## Practical GUI Tips

- Click hand cards to toggle selection.
- Watch the status line after every action; rule errors are shown there.
- The meld dropdown is mainly relevant when adding wild cards to an existing meld.
- If the stock/discard/meld areas look correct but card faces are missing, check the asset symlink or pass `--assets-dir`.
- If GTK bindings are not available in the current Python environment, the launcher attempts to re-exec using a system Python that has GTK4 installed.

## Screenshots

Suggested screenshot filenames:

- `docs/screenshots/main-window.png`
- `docs/screenshots/fanned-hand.png`
- `docs/screenshots/new-game-dialog.png`
- `docs/screenshots/add-to-meld.png`

These screenshots are now embedded above in the relevant sections.
