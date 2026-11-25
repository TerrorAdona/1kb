import { useEffect, useRef, useState } from "react";
import { getWebSocketTicket } from "./gameApi";

export type SocketState = "connecting" | "connected" | "disconnected" | "error";

export function useLobbySocket(
  gameId: string,
  onLobbyUpdate: () => void,
) {
  const [status, setStatus] = useState<SocketState>("connecting");
  const updateRef = useRef(onLobbyUpdate);
  updateRef.current = onLobbyUpdate;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;

    async function connect() {
      try {
        const ticket = await getWebSocketTicket(gameId);
        if (cancelled) return;

        const apiOrigin =
          import.meta.env.VITE_WS_BASE_URL ??
          (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1")
            .replace(/^http/, "ws");
        const socketUrl = new URL(ticket.websocket_path, apiOrigin);
        socketUrl.searchParams.set("ticket", ticket.ticket);
        socket = new WebSocket(socketUrl);

        socket.onopen = () => setStatus("connected");
        socket.onclose = () => setStatus("disconnected");
        socket.onerror = () => setStatus("error");
        socket.onmessage = (message) => {
          try {
            const payload: unknown = JSON.parse(message.data);
            if (
              payload &&
              typeof payload === "object" &&
              "type" in payload &&
              (payload.type === "lobby.snapshot" || payload.type === "lobby.event")
            ) {
              updateRef.current();
            }
          } catch {
            // Ignore malformed frames; snapshots are reloaded through REST.
          }
        };
      } catch {
        if (!cancelled) setStatus("error");
      }
    }

    void connect();
    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [gameId]);

  return status;
}
