/** Native (pywebview) mode detection.
 *
 *  When loaded inside a pywebview window, `window.pywebview` is injected
 *  before our React app hydrates (main.tsx awaits the `pywebviewready` event).
 *  All API methods that can fail return result envelopes:
 *  { ok: true, data } | { ok: false, error }.
 */

export interface NativeResult<T> {
  ok: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export interface NativeApi {
  index(): Promise<unknown>;
  feature(m: string, f: string): Promise<NativeResult<unknown>>;
  set_rule_status(
    m: string,
    f: string,
    ruleId: string,
    status: string,
  ): Promise<NativeResult<unknown>>;
  set_bug_status(
    m: string,
    f: string,
    bugId: string,
    status: string,
  ): Promise<NativeResult<unknown>>;
  resolve_finding(m: string, f: string, ruleQid: string): Promise<NativeResult<unknown>>;
  asset_root(): Promise<string>;
  open_window(ref: string | null): Promise<NativeResult<null>>;
}

declare global {
  interface Window {
    pywebview?: { api: NativeApi };
    __prdAssetRoot?: string;
    __prdOnFsEvent?: (e: { type: string; path?: string }) => void;
  }
}

// IMPORTANT: do not export IS_NATIVE as a module-level constant. pywebview
// injects `window.pywebview` *after* our ESM modules have evaluated, so a
// top-level read is always false. Use the function instead — it samples at
// call time.
export function isNative(): boolean {
  return typeof window !== "undefined" && !!window.pywebview;
}

export function nativeApi(): NativeApi {
  if (!window.pywebview) throw new Error("native bridge not available");
  return window.pywebview.api;
}
