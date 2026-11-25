import { useCallback, useEffect, useRef, useState } from "react";
import { getWebSocketTicket } from "./gameApi";
import type {
  GameSnapshot,
  GameSocketAck,
  LiveGameEvent,
} from "../../shared/types/realtime";

export type SocketState = "connecting" | "connected" | "disconnected" | "error";

export interface GameSocketHandlers {
  onSnapshot?: (snapshot: GameSnapshot) => void;
  onEvent?: (event: LiveGameEvent, snapshot: GameSnapshot) => void;
  onPresence?: (participantId: string, online: boolean) => void;
  onAck?: (ack: GameSocketAck) => void;
  onError?: (code: string, detail: string) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSnapshot(value: unknown): value is GameSnapshot {
  return (
    isRecord(value) &&
    isRecord(value.game) &&
    typeof value.game.id === "string" &&
    Array.isArray(value.events) &&
    isRecord(value.presence)
  );
}

export function useGameSocket(
  gameId: string,
  handlers: GameSocketHandlers,
  enabled = true,
) {
  const [status, setStatus] = useState<SocketState>("connecting");
  const socketRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!gameId || !enabled) {
      setStatus("disconnected");
      return;
    }

    let cancelled = false;
    let retryTimer: number | undefined;
    let retryCount = 0;

    const scheduleReconnect = () => {
      if (cancelled || retryTimer !== undefined) return;
      const delay = Math.min(750 * 2 ** retryCount, 10_000);
      retryCount += 1;
      retryTimer = window.setTimeout(() => {
        retryTimer = undefined;
        void connect();
      }, delay);
    };

    const connect = async () => {
      setStatus("connecting");
      try {
        const ticket = await getWebSocketTicket(gameId);
        if (cancelled) return;

        const apiOrigin =
          import.meta.env.VITE_WS_BASE_URL ??
          (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1")
            .replace(/^http/, "ws");
        const socketUrl = new URL(ticket.websocket_path, apiOrigin);
        socketUrl.searchParams.set("ticket", ticket.ticket);
        const socket = new WebSocket(socketUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          retryCount = 0;
          setStatus("connected");
        };
        socket.onerror = () => setStatus("error");
        socket.onclose = (event) => {
          if (socketRef.current === socket) socketRef.current = null;
          if (cancelled) return;
          if ([4403, 4404, 1008].includes(event.code)) {
            setStatus("error");
            return;
          }
          setStatus("disconnected");
          scheduleReconnect();
        };
        socket.onmessage = (message) => {
          let payload: unknown;
          try {
            payload = JSON.parse(message.data);
          } catch {
            return;
          }
          if (!isRecord(payload) || typeof payload.type !== "string") return;

          if (
            (payload.type === "game.snapshot" ||
              payload.type === "lobby.snapshot") &&
            isSnapshot(payload)
          ) {
            handlersRef.current.onSnapshot?.(payload);
          } else if (
            payload.type === "game.event" &&
            isSnapshot(payload) &&
            isRecord(payload.event)
          ) {
            handlersRef.current.onEvent?.(
              payload.event as unknown as LiveGameEvent,
              payload,
            );
          } else if (payload.type === "presence.changed") {
            if (
              typeof payload.participant_id === "string" &&
              typeof payload.online === "boolean"
            ) {
              handlersRef.current.onPresence?.(
                payload.participant_id,
                payload.online,
              );
            }
          } else if (payload.type === "game.ack") {
            handlersRef.current.onAck?.(payload as unknown as GameSocketAck);
          } else if (payload.type === "game.error") {
            handlersRef.current.onError?.(
              typeof payload.code === "string" ? payload.code : "game_error",
              typeof payload.detail === "string"
                ? payload.detail
                : "La commande n’a pas pu être traitée.",
            );
          }
        };
      } catch {
        if (cancelled) return;
        setStatus("error");
        scheduleReconnect();
      }
    };

    void connect();
    return () => {
      cancelled = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      const socket = socketRef.current;
      socketRef.current = null;
      socket?.close();
    };
  }, [enabled, gameId]);

  const send = useCallback((payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }, []);

  return { status, send };
}

export function useLobbySocket(
  gameId: string,
  onLobbyUpdate: () => void,
  onPresence?: (participantId: string, online: boolean) => void,
  onSnapshot?: (snapshot: GameSnapshot) => void,
) {
  const updateRef = useRef(onLobbyUpdate);
  const presenceRef = useRef(onPresence);
  const snapshotRef = useRef(onSnapshot);
  updateRef.current = onLobbyUpdate;
  presenceRef.current = onPresence;
  snapshotRef.current = onSnapshot;
  const { status } = useGameSocket(gameId, {
    onSnapshot: (snapshot) => {
      snapshotRef.current?.(snapshot);
      updateRef.current();
    },
    onEvent: (_event, snapshot) => {
      snapshotRef.current?.(snapshot);
      updateRef.current();
    },
    onPresence: (participantId, online) =>
      presenceRef.current?.(participantId, online),
  });
  return status;
}
