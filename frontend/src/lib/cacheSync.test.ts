import { describe, expect, it } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { patchIndexStatsFromFeature } from "./cacheSync";
import type { Feature, IndexPayload, Stats } from "@/types";

const baseStats: Stats = {
  rules_done: 7,
  rules_total: 10,
  bugs_open: 1,
  bugs_active: 1,
  ui_reviewed: 0,
  ui_total: 0,
};

const seed = (): IndexPayload => ({
  modules: [
    {
      name: "alpha",
      features: [
        {
          ref: "alpha/one",
          module: "alpha",
          feature: "one",
          name: "One",
          stats: baseStats,
          parse_ok: true,
        },
        {
          ref: "alpha/two",
          module: "alpha",
          feature: "two",
          name: "Two",
          stats: baseStats,
          parse_ok: true,
        },
      ],
    },
    {
      name: "beta",
      features: [
        {
          ref: "beta/x",
          module: "beta",
          feature: "x",
          name: "X",
          stats: baseStats,
          parse_ok: true,
        },
      ],
    },
  ],
});

const freshFeature = (stats: Stats): Feature => ({
  ref: "alpha/one",
  module: "alpha",
  feature: "one",
  name: "One",
  overview: "",
  implementations: [],
  requirements: [],
  bugs: [],
  stats,
});

describe("patchIndexStatsFromFeature", () => {
  it("replaces stats for the matching feature only", () => {
    const qc = new QueryClient();
    qc.setQueryData<IndexPayload>(["index"], seed());

    const newStats: Stats = { ...baseStats, rules_done: 8 };
    patchIndexStatsFromFeature(qc, freshFeature(newStats));

    const after = qc.getQueryData<IndexPayload>(["index"])!;
    expect(after.modules[0].features[0].stats.rules_done).toBe(8);
    // Sibling in same module unchanged.
    expect(after.modules[0].features[1].stats.rules_done).toBe(7);
    // Other module unchanged.
    expect(after.modules[1].features[0].stats.rules_done).toBe(7);
  });

  it("is a no-op when the index isn't in the cache yet", () => {
    const qc = new QueryClient();
    patchIndexStatsFromFeature(qc, freshFeature(baseStats));
    expect(qc.getQueryData(["index"])).toBeUndefined();
  });

  it("preserves identity for unaffected modules", () => {
    const qc = new QueryClient();
    const before = seed();
    qc.setQueryData<IndexPayload>(["index"], before);

    patchIndexStatsFromFeature(qc, freshFeature({ ...baseStats, rules_done: 9 }));

    const after = qc.getQueryData<IndexPayload>(["index"])!;
    // The "beta" module object reference is unchanged.
    expect(after.modules[1]).toBe(before.modules[1]);
  });
});
