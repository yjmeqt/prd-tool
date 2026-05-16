import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

// Module-level so api.ts can stamp the suppression window without prop-drilling.
let lastOwnWriteAt = 0;
export function noteOwnWrite(): void {
  lastOwnWriteAt = Date.now();
}

const OWN_WRITE_SUPPRESS_MS = 600;

export type ConnectionState = "connecting" | "open" | "error";

export function useSseInvalidation(): ConnectionState {
  const qc = useQueryClient();
  const [state, setState] = useState<ConnectionState>("connecting");

  useEffect(() => {
    const es = new EventSource("/api/events");
    const invalidate = () => {
      // Coalesce echoes of our own POSTs. The mutation's onSuccess has
      // already written the fresh payload into the cache; if SSE fires
      // again moments later, refetching just flickers the UI.
      if (Date.now() - lastOwnWriteAt < OWN_WRITE_SUPPRESS_MS) return;
      qc.invalidateQueries({ queryKey: ["index"] });
      qc.invalidateQueries({ queryKey: ["feature"] });
    };
    es.addEventListener("index_changed", invalidate);
    es.addEventListener("prd_changed", invalidate);
    es.addEventListener("invalid", invalidate);
    es.onopen = () => setState("open");
    es.onerror = () => setState("error");
    return () => es.close();
  }, [qc]);

  return state;
}
