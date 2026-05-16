import type { QueryClient } from "@tanstack/react-query";
import type { Feature, IndexPayload } from "@/types";

/**
 * Push the freshly-mutated feature's stats into the cached index payload so
 * the sidebar updates synchronously with the feature page after a local edit.
 *
 * The index query is also invalidated by the caller, but invalidate triggers
 * an async refetch — meanwhile SSE own-write suppression discards the
 * file-watcher echo, so without this patch the sidebar would briefly disagree
 * with the feature page. (See R11.indicators_match_stats / bug
 * sidebar_active_progress_wrong.)
 */
export function patchIndexStatsFromFeature(qc: QueryClient, fresh: Feature): void {
  qc.setQueryData<IndexPayload>(["index"], (old) => {
    if (!old) return old;
    return {
      modules: old.modules.map((m) => {
        if (m.name !== fresh.module) return m;
        return {
          ...m,
          features: m.features.map((f) =>
            f.feature === fresh.feature ? { ...f, stats: fresh.stats } : f,
          ),
        };
      }),
    };
  });
}
