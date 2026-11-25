"""Automatic, asynchronous execution of a bot's engine turn."""

from __future__ import annotations

import asyncio
import inspect
import random
from collections.abc import Awaitable, Callable, Mapping

from domain.game_engine import (
    ActionType,
    GamePhase,
    GameState,
    Transition,
    apply_action,
    legal_plays,
)

from .models import AIConfig
from .observation import build_observation
from .strategies import choose_action

WaitFunction = Callable[[float], Awaitable[None]]
TransitionCallback = Callable[[Transition], object | Awaitable[object]]


def is_bot_turn(state: GameState, player_id: str) -> bool:
    """Whether this player is expected to act in the current engine phase."""
    player_id = str(player_id)
    if state.phase in (GamePhase.DRAW, GamePhase.ACTION):
        return state.active_player.player_id == player_id
    if state.phase == GamePhase.RESPONSE:
        return state.pending_response_player_id == player_id
    return False


async def drive_automatic_turn(
    state: GameState,
    bot_configs: Mapping[str, AIConfig],
    *,
    rngs: Mapping[str, random.Random] | None = None,
    wait: WaitFunction = asyncio.sleep,
    on_transition: TransitionCallback | None = None,
) -> GameState:
    """Dispatch the current turn to its bot, or leave a human turn untouched.

    A game service can call this after every committed engine transition. The
    seat map is server-owned and should be built from bot participants, not
    accepted from a client request.
    """
    if state.phase == GamePhase.FINISHED:
        return state
    player_id = (
        state.pending_response_player_id
        if state.phase == GamePhase.RESPONSE
        else state.active_player.player_id
    )
    if player_id is None or player_id not in bot_configs:
        return state
    return await drive_bot_turn(
        state,
        player_id,
        config=bot_configs[player_id],
        rng=(rngs or {}).get(player_id),
        wait=wait,
        on_transition=on_transition,
    )


async def drive_bot_turn(
    state: GameState,
    player_id: str,
    *,
    config: AIConfig | None = None,
    rng: random.Random | None = None,
    wait: WaitFunction = asyncio.sleep,
    on_transition: TransitionCallback | None = None,
) -> GameState:
    """Play a bot's turn, including its draw, action and Coup-Fourré response.

    The caller should invoke this after a state transition whenever the active
    seat or pending-response seat is a bot. The optional callback receives each
    authoritative transition so an application can persist and broadcast it.
    A zero delay and an injected RNG/waiter make tests fully deterministic.
    """
    player_id = str(player_id)
    config = config or AIConfig()
    random_source = rng or random.Random(config.seed)
    current = state

    while is_bot_turn(current, player_id):
        observation = build_observation(current, player_id)
        if config.thinking_delay_seconds:
            await wait(config.thinking_delay_seconds)

        command = choose_action(
            observation,
            legal_plays(current, player_id),
            difficulty=config.difficulty,
            rng=random_source,
        )
        transition = apply_action(
            current,
            player_id=player_id,
            **command.to_engine_kwargs(),
        )
        current = transition.state

        if on_transition is not None:
            result = on_transition(transition)
            if inspect.isawaitable(result):
                await result

    return current
