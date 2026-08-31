import { useEffect, useState, useCallback } from "react";

// Every screen here is "read data, show it, occasionally act on it" -
// a WebSocket/SSE push channel would be the right call at real scale, but
// for a handful of admins polling every few seconds is simpler to build,
// simpler to reason about, and indistinguishable in the demo.
export function usePolling(fetchFn, intervalMs = 3000, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
