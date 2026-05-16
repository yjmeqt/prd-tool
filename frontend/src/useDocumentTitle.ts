import { useEffect } from "react";

const SUFFIX = "PRD Dashboard";

export function useDocumentTitle(parts: (string | undefined | null)[]): void {
  useEffect(() => {
    const trimmed = parts.filter(Boolean).map(String);
    document.title = trimmed.length ? `${trimmed.join(" · ")} · ${SUFFIX}` : SUFFIX;
  }, [parts.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
}
