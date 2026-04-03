from __future__ import annotations

import random
from dataclasses import dataclass

from canasta.model import (
    DRAW_COUNT_PER_TURN,
    Card,
    GameState,
    Meld,
    PlayerId,
    PlayerState,
    build_double_deck,
)
from canasta.rules import (
    can_add_cards_to_meld,
    can_discard,
    meld_score,
    red_three_score,
)


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class ActionResult:
    message: str


class CanastaEngine:
    def __init__(self, seed: int | None = None) -> None:
        deck = build_double_deck()
        random.Random(seed).shuffle(deck)

        north = PlayerState(hand=[], melds=[])
        south = PlayerState(hand=[], melds=[])
        for _ in range(11):
            north.hand.append(deck.pop())
            south.hand.append(deck.pop())

        discard = [deck.pop()]
        self.state = GameState(
            players={PlayerId.NORTH: north, PlayerId.SOUTH: south},
            current_player=PlayerId.NORTH,
            stock=deck,
            discard=discard,
            turn_drawn=False,
        )
        # Auto-meld red threes dealt into opening hands.
        for player in self.state.players.values():
            self._collect_red_threes(player)

    def current_hand(self) -> list[Card]:
        return self.state.players[self.state.current_player].hand

    def draw_stock(self) -> ActionResult:
        if self.state.turn_drawn:
            raise RuleError("you already drew this turn")
        if len(self.state.stock) < DRAW_COUNT_PER_TURN:
            raise RuleError("not enough cards in stock")

        hand = self.current_hand()
        for _ in range(DRAW_COUNT_PER_TURN):
            hand.append(self.state.stock.pop())
        self.state.turn_drawn = True

        player = self.state.players[self.state.current_player]
        auto = self._collect_red_threes(player)
        suffix = (
            f" ({auto} red three{'s' if auto != 1 else ''} auto-melded)" if auto else ""
        )
        return ActionResult(message=f"drew 2 cards{suffix}")

    def create_meld(self, hand_indexes: list[int]) -> ActionResult:
        player = self.state.players[self.state.current_player]
        if not self.state.turn_drawn:
            raise RuleError("draw before melding")
        if not hand_indexes:
            raise RuleError("select cards for meld")

        cards = self._pop_cards_from_hand(player.hand, hand_indexes)
        from canasta.rules import validate_meld_cards

        ok, reason = validate_meld_cards(cards)
        if not ok:
            player.hand.extend(cards)
            raise RuleError(reason)

        player.melds.append(Meld(cards=cards))
        return ActionResult(message="created meld")

    def add_to_meld(self, meld_index: int, hand_indexes: list[int]) -> ActionResult:
        player = self.state.players[self.state.current_player]
        if not self.state.turn_drawn:
            raise RuleError("draw before melding")
        if meld_index < 0 or meld_index >= len(player.melds):
            raise RuleError("invalid meld index")

        cards = self._pop_cards_from_hand(player.hand, hand_indexes)
        meld = player.melds[meld_index]
        ok, reason = can_add_cards_to_meld(meld, cards)
        if not ok:
            player.hand.extend(cards)
            raise RuleError(reason)

        meld.cards.extend(cards)
        return ActionResult(message="added cards to meld")

    def discard(self, hand_index: int) -> ActionResult:
        if not self.state.turn_drawn:
            raise RuleError("draw before discarding")

        hand = self.current_hand()
        if hand_index < 0 or hand_index >= len(hand):
            raise RuleError("invalid hand index")

        card = hand.pop(hand_index)
        ok, reason = can_discard(card)
        if not ok:
            hand.insert(hand_index, card)
            raise RuleError(reason)

        self.state.discard.append(card)
        self._check_winner()
        self._end_turn()
        return ActionResult(message=f"discarded {card.label()}")

    def score(self, player_id: PlayerId) -> int:
        player = self.state.players[player_id]
        return meld_score(player.melds) + red_three_score(player.red_threes)

    def _end_turn(self) -> None:
        self.state.turn_drawn = False
        self.state.current_player = (
            PlayerId.SOUTH
            if self.state.current_player == PlayerId.NORTH
            else PlayerId.NORTH
        )

    def _check_winner(self) -> None:
        player = self.state.players[self.state.current_player]
        if player.hand:
            return
        if any(meld.is_canasta for meld in player.melds):
            self.state.winner = self.state.current_player

    def _collect_red_threes(self, player: PlayerState) -> int:
        """Move red threes from hand to player.red_threes, drawing replacements.

        Loops until no red threes remain in the hand (a replacement could itself
        be a red three). Returns total count collected.
        """
        collected = 0
        while True:
            found = [c for c in player.hand if c.is_red_three()]
            if not found:
                break
            for card in found:
                player.hand.remove(card)
                player.red_threes.append(card)
                collected += 1
                if self.state.stock:
                    player.hand.append(self.state.stock.pop())
        return collected

    @staticmethod
    def _pop_cards_from_hand(hand: list[Card], indexes: list[int]) -> list[Card]:
        if not indexes:
            raise RuleError("no card indexes provided")
        unique_indexes = sorted(set(indexes), reverse=True)
        if len(unique_indexes) != len(indexes):
            raise RuleError("duplicate card indexes")
        cards: list[Card] = []
        for idx in unique_indexes:
            if idx < 0 or idx >= len(hand):
                raise RuleError("invalid hand index")
            cards.append(hand.pop(idx))
        cards.reverse()
        return cards
