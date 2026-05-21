import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

describe("api native bridge", () => {
  beforeEach(() => {
    vi.resetModules();
    (window as unknown as Record<string, unknown>).pywebview = {
      api: {
        index: vi.fn().mockResolvedValue({ modules: [] }),
        feature: vi.fn().mockResolvedValue({ ok: true, data: { module: "m", feature: "f" } }),
        set_rule_status: vi
          .fn()
          .mockResolvedValue({ ok: true, data: { module: "m", feature: "f" } }),
        set_bug_status: vi.fn(),
        resolve_finding: vi.fn(),
        asset_root: vi.fn().mockResolvedValue("/tmp/prd"),
        open_window: vi.fn(),
      },
    };
  });

  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).pywebview;
  });

  it("routes index() through window.pywebview.api.index", async () => {
    const { api } = await import("./api");
    await api.index();
    expect(
      (window as unknown as { pywebview: { api: Record<string, ReturnType<typeof vi.fn>> } })
        .pywebview.api.index,
    ).toHaveBeenCalled();
  });

  it("unwraps {ok,data} envelope for feature()", async () => {
    const { api } = await import("./api");
    const out = (await api.feature("m", "f")) as { module: string };
    expect(out.module).toBe("m");
  });

  it("throws ApiError on {ok:false}", async () => {
    (
      window as unknown as { pywebview: { api: Record<string, ReturnType<typeof vi.fn>> } }
    ).pywebview.api.feature = vi
      .fn()
      .mockResolvedValue({ ok: false, error: { code: "not_found", message: "x" } });
    const { api, ApiError } = await import("./api");
    await expect(api.feature("m", "f")).rejects.toBeInstanceOf(ApiError);
  });
});
