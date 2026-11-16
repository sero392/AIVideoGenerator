import { useEffect, useRef } from "react";

import type { ServerEvent } from "@/types/api";

/**
 * In-app bus for backend WebSocket events. The single socket lives in AppLayout
 * and publishes here; any page can subscribe without opening its own socket.
 */
const bus = new EventTarget();

export function publishServerEvent(event: ServerEvent): void {
  bus.dispatchEvent(new CustomEvent<ServerEvent>("server-event", { detail: event }));
}

export function useServerEvent(handler: (event: ServerEvent) => void): void {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const listener = (e: Event) => ref.current((e as CustomEvent<ServerEvent>).detail);
    bus.addEventListener("server-event", listener);
    return () => bus.removeEventListener("server-event", listener);
  }, []);
}
