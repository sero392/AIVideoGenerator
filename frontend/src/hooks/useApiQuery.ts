import { useCallback, useEffect, useRef, useState } from "react";

interface QueryState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refetch: () => void;
}

/**
 * Minimal fetch hook with abort + optional polling.
 * (Swap for TanStack Query once the app has many endpoints.)
 */
export function useApiQuery<T>(fetcher: (signal: AbortSignal) => Promise<T>, pollMs?: number): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetcherRef
      .current(controller.signal)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [tick]);

  useEffect(() => {
    if (!pollMs) return;
    const id = window.setInterval(refetch, pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refetch]);

  return { data, error, loading, refetch };
}
