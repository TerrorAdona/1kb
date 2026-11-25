import asyncio
import random

from domain.game_ai import (
    AIConfig,
    Difficulty,
    build_observation,
    choose_action,
    drive_automatic_turn,
    drive_bot_turn,
    is_bot_turn,
)
from domain.game_engine import (
    ActionType,
    Card,
    CardType,
    GamePhase,
    GameState,
    PlayerState,
    RulesConfig,
    apply_action,
    legal_plays,
    new_game,
)


def card(card_type: CardType, card_id: str) -> Card:
    return Card(id=card_id, card_type=card_type)


def make_state(
    *,
    hands: dict[str, list[Card]] | None = None,
    distances: dict[str, list[Card]] | None = None,
    draw: list[Card] | None = None,
    discard: list[Card] | None = None,
    phase: GamePhase = GamePhase.ACTION,
    active: str = "bot",
    pending_response_player_id: str | None = None,
    pending_response_attack: Card | None = None,
    rules: RulesConfig | None = None,
) -> GameState:
    hands = hands or {}
    distances = distances or {}
    player_ids = ("bot", "human", "other")
    players = [
        PlayerState(
            player_id=player_id,
            hand=list(hands.get(player_id, [])),
            distance_cards=list(distances.get(player_id, [])),
        )
        for player_id in player_ids
    ]
    return GameState(
        players=players,
        draw_pile=list(draw or []),
        discard_pile=list(discard or []),
        active_player_index=player_ids.index(active),
        phase=phase,
        rules=rules or RulesConfig(end_when_no_distance_cards=False),
        pending_response_player_id=pending_response_player_id,
        pending_response_attack=pending_response_attack,
    )


def test_easy_strategy_returns_an_engine_accepted_command():
    game = new_game(["bot", "human"], seed=31)
    rng = random.Random(81)

    for _ in range(20):
        if game.phase == GamePhase.FINISHED:
            break
        actor = (
            game.pending_response_player_id
            if game.phase == GamePhase.RESPONSE
            else game.active_player.player_id
        )
        observation = build_observation(game, actor)
        command = choose_action(
            observation,
            legal_plays(game, actor),
            difficulty=Difficulty.EASY,
            rng=rng,
        )
        game = apply_action(
            game,
            player_id=actor,
            **command.to_engine_kwargs(),
        ).state


def test_strategy_does_not_receive_hidden_opponent_hands_or_draw_contents():
    own = [card(CardType.KM_50, "own")]
    first = make_state(
        hands={
            "bot": own,
            "human": [card(CardType.ACCIDENT, "secret-a")],
            "other": [card(CardType.KM_200, "secret-b")],
        },
        draw=[card(CardType.DRIVING_ACE, "draw-a")],
    )
    second = make_state(
        hands={
            "bot": own,
            "human": [card(CardType.FUEL, "secret-c")],
            "other": [card(CardType.RED_LIGHT, "secret-d")],
        },
        draw=[card(CardType.KM_25, "draw-b")],
    )

    first_view = build_observation(first, "bot")
    second_view = build_observation(second, "bot")

    assert first_view == second_view
    assert not hasattr(first_view, "draw_pile")
    assert all(not hasattr(player, "hand") for player in first_view.opponents)
    assert first_view.hand == (own[0],)


def test_seeded_choices_are_reproducible():
    game = make_state(
        hands={
            "bot": [
                card(CardType.KM_25, "25"),
                card(CardType.KM_50, "50"),
                card(CardType.KM_75, "75"),
            ]
        }
    )
    observation = build_observation(game, "bot")
    plays = legal_plays(game, "bot")

    first = choose_action(
        observation,
        plays,
        difficulty=Difficulty.EASY,
        rng=random.Random(2026),
    )
    second = choose_action(
        observation,
        plays,
        difficulty=Difficulty.EASY,
        rng=random.Random(2026),
    )

    assert first == second


def test_normal_and_hard_choose_a_valid_repair_over_unrelated_play():
    state = make_state(
        hands={
            "bot": [
                card(CardType.REPAIRS, "repair"),
                card(CardType.KM_100, "distance"),
            ]
        },
    )
    state.players[0].battle_attack = card(CardType.ACCIDENT, "accident")
    observation = build_observation(state, "bot")
    plays = legal_plays(state, "bot")

    for difficulty in (Difficulty.NORMAL, Difficulty.HARD):
        command = choose_action(
            observation,
            plays,
            difficulty=difficulty,
            rng=random.Random(7),
        )
        assert command.card_id == "repair"
        apply_action(state, player_id="bot", **command.to_engine_kwargs())


def test_every_difficulty_discards_only_when_engine_offers_no_play():
    state = make_state(
        hands={"bot": [card(CardType.KM_100, "blocked-distance")]},
    )
    state.players[0].battle_attack = card(CardType.ACCIDENT, "active-accident")
    observation = build_observation(state, "bot")
    plays = legal_plays(state, "bot")
    assert plays == ()

    for difficulty in Difficulty:
        command = choose_action(
            observation,
            plays,
            difficulty=difficulty,
            rng=random.Random(13),
        )
        assert command.action == ActionType.DISCARD
        apply_action(state, player_id="bot", **command.to_engine_kwargs())


def test_bot_driver_automatically_draws_and_plays_until_turn_ends():
    state = make_state(
        hands={"bot": [card(CardType.KM_100, "distance")]},
        draw=[card(CardType.KM_25, "drawn")],
        phase=GamePhase.DRAW,
    )
    delay_calls: list[float] = []

    async def fake_wait(delay: float) -> None:
        delay_calls.append(delay)

    final = asyncio.run(
        drive_bot_turn(
            state,
            "bot",
            config=AIConfig(
                difficulty=Difficulty.NORMAL,
                thinking_delay_seconds=0.25,
                seed=9,
            ),
            wait=fake_wait,
        )
    )

    assert final.players[0].distance == 100
    assert final.phase == GamePhase.DRAW
    assert final.active_player.player_id == "human"
    assert delay_calls == [0.25, 0.25]
    assert not is_bot_turn(final, "bot")


def test_automatic_dispatcher_runs_only_when_a_bot_owns_the_turn():
    state = make_state(
        hands={"bot": [card(CardType.KM_25, "distance")]},
        phase=GamePhase.DRAW,
    )
    bot_configs = {
        "bot": AIConfig(Difficulty.NORMAL, thinking_delay_seconds=0, seed=1)
    }

    human_turn = asyncio.run(drive_automatic_turn(state, {}))
    bot_turn = asyncio.run(drive_automatic_turn(state, bot_configs))

    assert human_turn is state
    assert bot_turn.active_player.player_id == "human"
    assert bot_turn.players[0].distance == 25


def test_bot_plays_a_coup_fourre_and_then_continues_its_turn():
    state = make_state(
        hands={
            "bot": [
                card(CardType.PRIORITY_VEHICLE, "safety"),
                card(CardType.KM_50, "distance"),
            ]
        },
        phase=GamePhase.RESPONSE,
        active="human",
        pending_response_player_id="bot",
        pending_response_attack=card(CardType.RED_LIGHT, "attack"),
    )

    final = asyncio.run(
        drive_bot_turn(
            state,
            "bot",
            config=AIConfig(thinking_delay_seconds=0, seed=4),
        )
    )

    assert CardType.PRIORITY_VEHICLE in final.players[0].safeties
    assert final.players[0].distance == 50
    assert final.active_player.player_id == "human"
    assert final.phase == GamePhase.DRAW


def test_full_bot_game_never_submits_an_invalid_engine_action():
    game = new_game(["easy", "normal", "hard"], seed=713)
    configs = {
        "easy": AIConfig(Difficulty.EASY, thinking_delay_seconds=0, seed=1),
        "normal": AIConfig(Difficulty.NORMAL, thinking_delay_seconds=0, seed=2),
        "hard": AIConfig(Difficulty.HARD, thinking_delay_seconds=0, seed=3),
    }

    for _ in range(300):
        if game.phase == GamePhase.FINISHED:
            break
        actor = (
            game.pending_response_player_id
            if game.phase == GamePhase.RESPONSE
            else game.active_player.player_id
        )
        game = asyncio.run(
            drive_bot_turn(
                game,
                actor,
                config=configs[actor],
            )
        )

    assert game.turn_number > 1 or game.phase == GamePhase.FINISHED
