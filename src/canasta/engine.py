from __future__ import annotations

import random
from dataclasses import dataclass

from canasta.hands import pop_cards_from_hand, sort_hand
from canasta.model import (
    DRAW_COUNT_PER_TURN,
    Card,
    GameState,
    Meld,
    PlayerId,
    PlayerState,
    RuleError,
)
from canasta.rules import (
    OPENING_MELD_MINIMUM,
    can_add_cards_to_meld,
    can_discard,
    can_pickup_frozen_discard,
    discard_pile_is_frozen,
    opening_meld_value,
    red_three_score,
)
from canasta.scoring import calculate_round_score, calculate_total_score
from canasta.turns import (
    build_round_state,
    check_winner,
    collect_red_threes,
    end_turn,
    ensure_round_active,
)


@dataclass(frozen=True)
class ActionResult:
    message: str


class CanastaEngine:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.state = self._build_round_state(
            scores={PlayerId.NORTH: 0, PlayerId.SOUTH: 0},
            starting_player=PlayerId.NORTH,
            round_number=1,
        )

    def current_hand(self) -> list[Card]:
        return self.state.players[self.state.current_player].hand

    def next_round(self) -> ActionResult:
        if self.state.winner is None:
            raise RuleError("round is not over")

        scores = {
            player_id: player.score + self.score(player_id)
            for player_id, player in self.state.players.items()
        }
        winner = self.state.winner
        self.state = self._build_round_state(
            scores=scores,
            starting_player=winner,
            round_number=self.state.round_number + 1,
        )
        return ActionResult(message=f"started round {self.state.round_number}")

    def draw_stock(self) -> ActionResult:
        ensure_round_active(self.state)
        if self.state.turn_drawn:
            raise RuleError("you already drew this turn")
        if len(self.state.stock) < DRAW_COUNT_PER_TURN:
            raise RuleError("not enough cards in stock")

        hand = self.current_hand()
        for _ in range(DRAW_COUNT_PER_TURN):
            hand.append(self.state.stock.pop())
        self.state.turn_drawn = True

        player = self.state.players[self.state.current_player]
        auto = collect_red_threes(player, self.state.stock)
        sort_hand(player.hand)
        suffix = (
            f" ({auto} red three{'s' if auto != 1 else ''} auto-melded)" if auto else ""
        )
        return ActionResult(message=f"drew 2 cards{suffix}")

    def pickup_discard(self, hand_indexes: list[int]) -> ActionResult:
        ensure_round_active(self.state)
        player = self.state.players[self.state.current_player]
        if self.state.turn_drawn:
            raise RuleError("you already drew this turn")
        if not self.state.discard:
            raise RuleError("discard pile is empty")

        cards = pop_cards_from_hand(player.hand, hand_indexes)
        from canasta.rules import validate_meld_cards

        top_discard = self.state.discard[-1]
        if discard_pile_is_frozen(self.state.discard):
            ok, reason = can_pickup_frozen_discard(top_discard, cards)
            if not ok:
                player.hand.extend(cards)
                sort_hand(player.hand)
                raise RuleError(reason)

        meld_cards = cards + [top_discard]
        ok, reason = validate_meld_cards(meld_cards)
        if not ok:
            player.hand.extend(cards)
            sort_hand(player.hand)
            raise RuleError(f"cannot pick up discard pile: {reason}")

        if not player.melds:
            value = opening_meld_value(meld_cards)
            if value < OPENING_MELD_MINIMUM:
                player.hand.extend(cards)
                sort_hand(player.hand)
                raise RuleError(
                    f"opening meld must score at least {OPENING_MELD_MINIMUM} points "
                    f"(naturals only); this scores {value}"
                )

        pile = list(self.state.discard)
        player.melds.append(Meld(cards=meld_cards))
        self.state.discard.clear()
        player.hand.extend(pile[:-1])
        self.state.turn_drawn = True

        auto = collect_red_threes(player, self.state.stock)
        sort_hand(player.hand)
        suffix = (
            f" ({auto} red three{'s' if auto != 1 else ''} auto-melded)" if auto else ""
        )
        return ActionResult(
            message=f"picked up {len(pile)} discard pile card{'s' if len(pile) != 1 else ''} and created meld{suffix}"
        )

    def create_meld(self, hand_indexes: list[int]) -> ActionResult:
        ensure_round_active(self.state)
        player = self.state.players[self.state.current_player]
        if not self.state.turn_drawn:
            raise RuleError("draw before melding")
        if not hand_indexes:
            raise RuleError("select cards for meld")

        cards = pop_cards_from_hand(player.hand, hand_indexes)
        from canasta.rules import validate_meld_cards

        ok, reason = validate_meld_cards(cards)
        if not ok:
            player.hand.extend(cards)
            sort_hand(player.hand)
            raise RuleError(reason)

        if not player.melds:
            value = opening_meld_value(cards)
            if value < OPENING_MELD_MINIMUM:
                player.hand.extend(cards)
                sort_hand(player.hand)
                raise RuleError(
                    f"opening meld must score at least {OPENING_MELD_MINIMUM} points "
                    f"(naturals only); this scores {value}"
                )

        player.melds.append(Meld(cards=cards))
        return ActionResult(message="created meld")

    def add_to_meld(self, meld_index: int, hand_indexes: list[int]) -> ActionResult:
        ensure_round_active(self.state)
        player = self.state.players[self.state.current_player]
        if not self.state.turn_drawn:
            raise RuleError("draw before melding")
        if meld_index < 0 or meld_index >= len(player.melds):
            raise RuleError("invalid meld index")

        cards = pop_cards_from_hand(player.hand, hand_indexes)
        meld = player.melds[meld_index]
        ok, reason = can_add_cards_to_meld(meld, cards)
        if not ok:
            player.hand.extend(cards)
            sort_hand(player.hand)
            raise RuleError(reason)

        meld.cards.extend(cards)
        return ActionResult(message="added cards to meld")

    def discard(self, hand_index: int) -> ActionResult:
        ensure_round_active(self.state)
        if not self.state.turn_drawn:
            raise RuleError("draw before discarding")

        hand = self.current_hand()
        if hand_index < 0 or hand_index >= len(hand):
            raise RuleError("invalid hand index")

        card = hand.pop(hand_index)
        ok, reason = can_discard(card)
        if not ok:
            hand.insert(hand_index, card)
            sort_hand(hand)
            raise RuleError(reason)

        self.state.discard.append(card)
        check_winner(self.state)
        if self.state.winner is None:
            end_turn(self.state)
        return ActionResult(message=f"discarded {card.label()}")

    def score(self, player_id: PlayerId) -> int:
        player = self.state.players[player_id]
        return calculate_round_score(player, self.state.winner is not None)

    def total_score(self, player_id: PlayerId) -> int:
        player = self.state.players[player_id]
        round_over = self.state.winner is not None
        round_score = self.score(player_id)
        return calculate_total_score(player, round_over, round_score)

    def _build_round_state(
        self,
        scores: dict[PlayerId, int],
        starting_player: PlayerId,
        round_number: int,
    ) -> GameState:
        """Build a new round using the turns module helper."""
        return build_round_state(
            scores=scores,
            starting_player=starting_player,
            round_number=round_number,
            rng=self._rng,
            collect_red_threes_fn=collect_red_threes,
            sort_hand_fn=sort_hand,
        )
