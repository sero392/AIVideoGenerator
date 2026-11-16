import { useCallback, useEffect, useRef, useState } from "react";

interface QueryState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refetch: () => void;
}

interface QueryOptions {
  /** Re-fetch periodically (ms). */
  pollMs?: number;
  /** Re-fetch whenever any of these values change (e.g. filters). */
  deps?: readonly unknown[];
}

/**
 * Minimal fetch hook with abort, polling and dependency-driven refetch.
 * Previous data is kept while re-fetching so the UI does not flash.
 * (Swap for TanStack Query once the app has many endpoints.)
 */
export function useApiQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: QueryOptions | number = {},
): QueryState<T> {
  const { pollMs, deps = [] } = typeof options === "number" ? { pollMs: options } : options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(() => setTick((t) => t + 1), []);
  const depsKey = JSON.stringify(deps);

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
  }, [tick, depsKey]);

  useEffect(() => {
    if (!pollMs) return;
    const id = window.setInterval(refetch, pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refetch]);

  return { data, error, loading, refetch };
}
