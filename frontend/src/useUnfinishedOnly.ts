import { useCallback, useEffect, useState } from "react";

/**
 * Persisted "Show only unfinished" toggle.
 *
 * Stored in localStorage so the state survives navigation within the dashboard
 * session and reloads. Shared across the home rollup and every feature detail
 * page via the storage event, so toggling on one page updates the other.
 */
const KEY = "prd:unfinishedOnly";
const EVENT = "prd:unfinishedOnly:changed";

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function useUnfinishedOnly(): [boolean, (next: boolean) => void] {
  const [on, setOn] = useState<boolean>(() => read());

  useEffect(() => {
    const onChange = () => setOn(read());
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  const set = useCallback((next: boolean) => {
    try {
      window.localStorage.setItem(KEY, next ? "1" : "0");
    } catch {
      // ignore
    }
    setOn(next);
    window.dispatchEvent(new Event(EVENT));
  }, []);

  return [on, set];
}
