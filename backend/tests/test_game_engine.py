from collections import Counter

import pytest

from domain.game_engine import (
    ActionType,
    Card,
    CardType,
    GamePhase,
    GameState,
    PlayerState,
    RuleViolation,
    RulesConfig,
    apply_action,
    build_deck,
    calculate_scores,
    legal_plays,
    new_game,
    score_player,
    state_from_dict,
    state_to_dict,
)


def card(card_type: CardType, card_id: str) -> Card:
    return Card(id=card_id, card_type=card_type)


def state_with(
    *,
    hands: dict[str, list[Card]] | None = None,
    distances: dict[str, list[Card]] | None = None,
    battle_attacks: dict[str, Card] | None = None,
    speed_attacks: dict[str, Card] | None = None,
    safeties: dict[str, set[CardType]] | None = None,
    draw: list[Card] | None = None,
    phase: GamePhase = GamePhase.ACTION,
    active: str = "p1",
    rules: RulesConfig | None = None,
) -> GameState:
    player_ids = ["p1", "p2", "p3"]
    hands = hands or {}
    distances = distances or {}
    battle_attacks = battle_attacks or {}
    speed_attacks = speed_attacks or {}
    safeties = safeties or {}
    players = [
        PlayerState(
            player_id=player_id,
            hand=list(hands.get(player_id, [])),
            distance_cards=list(distances.get(player_id, [])),
            battle_attack=battle_attacks.get(player_id),
            speed_attack=speed_attacks.get(player_id),
            safeties=set(safeties.get(player_id, set())),
        )
        for player_id in player_ids
    ]
    return GameState(
        players=players,
        draw_pile=list(draw or []),
        discard_pile=[],
        active_player_index=player_ids.index(active),
        phase=phase,
        rules=rules or RulesConfig(end_when_no_distance_cards=False),
    )


def take_turn_action(state: GameState, player_id: str, card: Card) -> GameState:
    return apply_action(
        state, player_id=player_id, action=ActionType.PLAY, card_id=card.id
    ).state


def test_classic_deck_contains_106_playable_cards_with_expected_counts():
    deck = build_deck(id_factory=iter(map(str, range(200))).__next__)

    assert len(deck) == 106
    assert Counter(item.card_type for item in deck) == {
        CardType.KM_25: 10,
        CardType.KM_50: 10,
        CardType.KM_75: 10,
        CardType.KM_100: 12,
        CardType.KM_200: 4,
        CardType.SPEED_LIMIT: 4,
        CardType.RED_LIGHT: 5,
        CardType.OUT_OF_FUEL: 3,
        CardType.FLAT_TIRE: 3,
        CardType.ACCIDENT: 3,
        CardType.GREEN_LIGHT: 14,
        CardType.END_SPEED_LIMIT: 6,
        CardType.FUEL: 6,
        CardType.SPARE_TIRE: 6,
        CardType.REPAIRS: 6,
        CardType.PRIORITY_VEHICLE: 1,
        CardType.EXTRA_TANK: 1,
        CardType.PUNCTURE_PROOF: 1,
        CardType.DRIVING_ACE: 1,
    }


def test_new_game_deals_six_and_starts_with_the_selected_player():
    game = new_game(["p1", "p2"], seed=42)

    assert [len(player.hand) for player in game.players] == [6, 6]
    assert game.active_player.player_id == "p1"
    assert game.phase == GamePhase.DRAW
    assert len(game.draw_pile) == 94


def test_draw_is_private_and_only_current_player_can_draw():
    game = new_game(["p1", "p2"], seed=5)

    with pytest.raises(RuleViolation, match="Ce n’est pas votre tour"):
        apply_action(game, player_id="p2", action=ActionType.DRAW)
    with pytest.raises(RuleViolation) as error:
        apply_action(
            game,
            player_id="p1",
            action=ActionType.PLAY,
            card_id=game.players[0].hand[0].id,
        )
    assert error.value.code == "draw_required"
    assert len(game.players[0].hand) == 6

    transition = apply_action(game, player_id="p1", action=ActionType.DRAW)
    assert len(transition.state.players[0].hand) == 7
    assert transition.state.phase == GamePhase.ACTION
    assert transition.events[0].private_to_player_id == "p1"
    assert len(game.players[0].hand) == 6  # Commands do not mutate their input.


def test_frontend_cannot_play_a_card_not_in_the_authoritative_hand():
    game = state_with(hands={"p1": [card(CardType.KM_25, "actual")]})

    with pytest.raises(RuleViolation) as error:
        apply_action(
            game, player_id="p1", action="play", card_id="forged-card-id"
        )

    assert error.value.code == "card_not_in_hand"
    assert game.players[0].hand[0].id == "actual"


def test_distance_cards_can_start_without_green_light_in_2025_rules():
    km25 = card(CardType.KM_25, "km25")
    game = state_with(hands={"p1": [km25]})

    assert [play.card_id for play in legal_plays(game, "p1")] == ["km25"]
    result = take_turn_action(game, "p1", km25)

    assert result.players[0].distance == 25
    assert result.phase == GamePhase.DRAW


def test_distance_cannot_exceed_1000_and_exact_1000_wins():
    p1_km = [
        card(CardType.KM_200, "p1-200-a"),
        card(CardType.KM_200, "p1-200-b"),
        *[card(CardType.KM_100, f"p1-100-{index}") for index in range(5)],
    ]
    game = state_with(
        hands={
            "p1": [
                card(CardType.KM_100, "finish"),
                card(CardType.KM_25, "over"),
            ]
        },
        distances={"p1": p1_km},
    )
    result = take_turn_action(game, "p1", game.players[0].hand[0])
    assert result.phase == GamePhase.FINISHED
    assert result.winner_ids == ["p1"]
    assert result.finish_reason == "target_distance"
    assert score_player(result, "p1") == 1000


def test_third_200_km_card_is_not_a_legal_play():
    existing = [card(CardType.KM_200, f"used-{i}") for i in range(2)]
    third = card(CardType.KM_200, "third")
    game = state_with(hands={"p1": [third]}, distances={"p1": existing})

    assert legal_plays(game, "p1") == ()
    with pytest.raises(RuleViolation) as error:
        take_turn_action(game, "p1", third)
    assert error.value.code == "too_many_200_cards"


def test_speed_limit_blocks_more_than_50_km_but_allows_25_and_50():
    km25 = card(CardType.KM_25, "km25")
    km50 = card(CardType.KM_50, "km50")
    km75 = card(CardType.KM_75, "km75")
    limit = card(CardType.SPEED_LIMIT, "limit")
    game = state_with(
        hands={"p1": [km25, km50, km75]},
        speed_attacks={"p1": limit},
    )

    assert {play.card_id for play in legal_plays(game, "p1")} == {"km25", "km50"}
    with pytest.raises(RuleViolation) as error:
        take_turn_action(game, "p1", km75)
    assert error.value.code == "speed_limit"


def test_attack_requires_target_to_be_rolling_and_sets_battle_hazard():
    attack = card(CardType.RED_LIGHT, "red")
    game = state_with(hands={"p1": [attack]})

    with pytest.raises(RuleViolation) as error:
        apply_action(
            game,
            player_id="p1",
            action="play",
            card_id="red",
            target_player_id="p2",
        )
    assert error.value.code == "target_not_rolling"

    game.players[1].distance_cards.append(card(CardType.KM_25, "p2-km"))
    result = apply_action(
        game,
        player_id="p1",
        action="play",
        card_id="red",
        target_player_id="p2",
    ).state
    assert result.phase == GamePhase.RESPONSE
    assert result.pending_response_player_id == "p2"
    assert result.players[1].battle_attack == attack


def test_matching_parade_repairs_attack_and_allows_movement_without_new_green():
    green = card(CardType.GREEN_LIGHT, "green")
    km50 = card(CardType.KM_50, "km50")
    red = card(CardType.RED_LIGHT, "red")
    game = state_with(
        hands={"p1": [green, km50]},
        battle_attacks={"p1": red},
    )

    repaired = take_turn_action(game, "p1", green)
    assert repaired.players[0].battle_attack is None
    assert repaired.phase == GamePhase.DRAW
    repaired.active_player_index = 0
    repaired.phase = GamePhase.ACTION
    advanced = take_turn_action(repaired, "p1", km50)
    assert advanced.players[0].distance == 50


def test_coup_fourre_clears_attack_draws_twice_and_grants_immediate_replay():
    priority = card(CardType.PRIORITY_VEHICLE, "priority")
    red = card(CardType.RED_LIGHT, "red")
    draw_cards = [
        card(CardType.KM_50, "draw-1"),
        card(CardType.KM_75, "draw-2"),
        card(CardType.KM_25, "draw-3"),
    ]
    game = state_with(
        hands={"p1": [red], "p2": [priority]},
        distances={"p2": [card(CardType.KM_25, "p2-distance")]},
        draw=draw_cards,
    )
    attacked = apply_action(
        game,
        player_id="p1",
        action="play",
        card_id="red",
        target_player_id="p2",
    ).state

    result = apply_action(
        attacked,
        player_id="p2",
        action="play",
        card_id="priority",
    )

    assert result.state.active_player.player_id == "p2"
    assert result.state.phase == GamePhase.ACTION
    assert result.state.players[1].battle_attack is None
    assert CardType.PRIORITY_VEHICLE in result.state.players[1].safeties
    assert result.state.players[1].coup_fourres == 1
    assert [item.id for item in result.state.players[1].hand] == [
        "draw-1",
        "draw-2",
    ]
    assert [event.details.get("reason") for event in result.events if event.event_type == "card.drawn"] == [
        "coup_fourre_refill",
        "coup_fourre_replay",
    ]
    assert result.state.active_player.player_id != "p3"


def test_coup_fourre_responds_to_the_latest_speed_limit_even_with_another_attack():
    speed_limit = card(CardType.SPEED_LIMIT, "speed")
    priority = card(CardType.PRIORITY_VEHICLE, "priority")
    older_attack = card(CardType.OUT_OF_FUEL, "fuel-attack")
    game = state_with(
        hands={"p1": [speed_limit], "p2": [priority]},
        distances={"p2": [card(CardType.KM_25, "p2-km")]},
        battle_attacks={"p2": older_attack},
        draw=[
            card(CardType.KM_25, "draw-1"),
            card(CardType.KM_50, "draw-2"),
        ],
    )

    attacked = apply_action(
        game,
        player_id="p1",
        action="play",
        card_id="speed",
        target_player_id="p2",
    ).state
    assert attacked.pending_response_attack == speed_limit
    assert [play.card_id for play in legal_plays(attacked, "p2")] == ["priority"]

    result = apply_action(
        attacked, player_id="p2", action="play", card_id="priority"
    ).state

    assert result.players[1].speed_attack is None
    # The Priority Vehicle answers the Speed Limit, not the older breakdown.
    assert result.players[1].battle_attack == older_attack
    assert result.phase == GamePhase.ACTION
    assert result.active_player.player_id == "p2"


def test_wrong_player_cannot_answer_coup_fourre():
    game = state_with(
        hands={"p1": [card(CardType.RED_LIGHT, "red")]},
        distances={"p2": [card(CardType.KM_25, "p2-km")]},
    )
    attacked = apply_action(
        game,
        player_id="p1",
        action="play",
        card_id="red",
        target_player_id="p2",
    ).state

    with pytest.raises(RuleViolation) as error:
        apply_action(attacked, player_id="p3", action="pass")
    assert error.value.code == "not_response_player"


def test_priority_vehicle_prevents_red_light_and_speed_limit_attacks():
    priority = CardType.PRIORITY_VEHICLE
    red = card(CardType.RED_LIGHT, "red")
    game = state_with(
        hands={"p1": [red]},
        distances={"p2": [card(CardType.KM_25, "p2-km")]},
        safeties={"p2": {priority}},
    )

    with pytest.raises(RuleViolation) as error:
        apply_action(
            game,
            player_id="p1",
            action="play",
            card_id="red",
            target_player_id="p2",
        )
    assert error.value.code == "target_protected"


def test_discard_is_only_allowed_when_no_card_is_playable():
    km25 = card(CardType.KM_25, "km25")
    km50 = card(CardType.KM_50, "km50")
    game = state_with(hands={"p1": [km25, km50]})

    with pytest.raises(RuleViolation) as error:
        apply_action(game, player_id="p1", action="discard", card_id="km25")
    assert error.value.code == "discard_not_allowed"

    stopped = state_with(
        hands={"p1": [km25]},
        battle_attacks={"p1": card(CardType.ACCIDENT, "accident")},
    )
    result = apply_action(
        stopped, player_id="p1", action="discard", card_id="km25"
    ).state
    assert result.players[0].hand == []
    assert result.discard_pile == [km25]


def test_distance_pile_empty_ends_at_end_of_action_and_preserves_ties():
    game = state_with(
        hands={"p1": [card(CardType.KM_25, "discard")]},
        distances={
            "p1": [card(CardType.KM_100, "p1-distance")],
            "p2": [card(CardType.KM_100, "p2-distance")],
        },
        draw=[card(CardType.FUEL, "non-distance")],
        rules=RulesConfig(allow_voluntary_discard=True),
    )

    result = apply_action(
        game, player_id="p1", action="discard", card_id="discard"
    ).state

    assert result.phase == GamePhase.FINISHED
    assert result.winner_ids == ["p1", "p2"]
    assert result.winner_id is None
    assert result.finish_reason == "distance_pile_empty"


def test_legacy_green_light_start_and_after_repair_are_configurable():
    rules = RulesConfig(
        start_requires_green_light=True,
        require_green_after_repair=True,
        end_when_no_distance_cards=False,
    )
    green = card(CardType.GREEN_LIGHT, "green")
    km25 = card(CardType.KM_25, "km25")
    game = state_with(hands={"p1": [green, km25]}, rules=rules)

    assert [play.card_id for play in legal_plays(game, "p1")] == ["green"]
    started = take_turn_action(game, "p1", green)
    assert started.players[0].has_green_light is True
    assert len(started.discard_pile) == 0

    fuel = card(CardType.FUEL, "fuel")
    repairs = state_with(
        hands={
            "p1": [
                fuel,
                card(CardType.GREEN_LIGHT, "resume"),
                card(CardType.KM_50, "km50"),
            ]
        },
        distances={"p1": [card(CardType.KM_25, "p1-km")]},
        battle_attacks={"p1": card(CardType.OUT_OF_FUEL, "out-of-fuel")},
        rules=rules,
    )
    fixed = take_turn_action(repairs, "p1", fuel)
    assert fixed.players[0].must_play_green_light is True
    fixed.active_player_index = 0
    fixed.phase = GamePhase.ACTION
    assert [play.card_id for play in legal_plays(fixed, "p1")] == ["resume"]
    restarted = take_turn_action(fixed, "p1", fixed.players[0].hand[0])
    assert restarted.players[0].must_play_green_light is False
    assert restarted.players[0].has_green_light is True


def test_json_snapshot_round_trip_keeps_rules_cards_and_phase():
    game = new_game(["p1", "p2"], seed=123)
    restored = state_from_dict(state_to_dict(game))

    assert restored.rules == game.rules
    assert restored.phase == game.phase
    assert [card.id for card in restored.players[0].hand] == [
        card.id for card in game.players[0].hand
    ]
    assert [card.id for card in restored.draw_pile] == [
        card.id for card in game.draw_pile
    ]

    pending = state_with(
        hands={"p1": [card(CardType.RED_LIGHT, "red")]},
        distances={"p2": [card(CardType.KM_25, "p2-km")]},
    )
    attacked = apply_action(
        pending,
        player_id="p1",
        action=ActionType.PLAY,
        card_id="red",
        target_player_id="p2",
    ).state
    restored_response = state_from_dict(state_to_dict(attacked))
    assert restored_response.pending_response_player_id == "p2"
    assert restored_response.pending_response_attack == card(CardType.RED_LIGHT, "red")


def test_score_is_kilometers_in_the_2025_ruleset():
    game = state_with(
        distances={"p1": [card(CardType.KM_100, "km"), card(CardType.KM_50, "km2")]}
    )

    assert score_player(game, "p1") == 150
    assert calculate_scores(game) == {"p1": 150, "p2": 0, "p3": 0}
