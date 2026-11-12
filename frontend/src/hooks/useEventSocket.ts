import { useEffect, useState } from "react";

import { eventsSocketUrl } from "@/services/api";
import type { ServerEvent } from "@/types/api";

export type SocketState = "connecting" | "open" | "closed";

/** Connects to the backend event stream and reconnects with backoff. */
export function useEventSocket(onEvent?: (event: ServerEvent) => void): SocketState {
  const [state, setState] = useState<SocketState>("connecting");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let disposed = false;

    const connect = () => {
      setState("connecting");
      socket = new WebSocket(eventsSocketUrl());
      socket.onopen = () => {
        retry = 0;
        setState("open");
      };
      socket.onmessage = (msg) => {
        try {
          onEvent?.(JSON.parse(msg.data) as ServerEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        setState("closed");
        const delay = Math.min(30_000, 1_000 * 2 ** retry++);
        timer = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
    // onEvent intentionally excluded: reconnecting on every render would be wrong.
  }, []);

  return state;
}
