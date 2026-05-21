import { Feature, IndexPayload } from "./types";
import { noteOwnWrite } from "./useSse";
import { IS_READONLY, STATIC_BASE } from "./lib/staticMode";
import { isNative, nativeApi, NativeResult } from "./lib/nativeMode";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: body == null ? {} : { "content-type": "application/json" },
    body: body == null ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let detail: unknown = await r.text();
    try {
      detail = JSON.parse(detail as string);
    } catch {
      // not JSON, keep as text
    }
    throw new ApiError(r.status, detail);
  }
  noteOwnWrite();
  return r.json();
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function readOnlyReject<T>(): Promise<T> {
  return Promise.reject(
    new ApiError(0, { code: "read_only", message: "Dashboard is in read-only mode" }),
  );
}

function unwrap<T>(r: NativeResult<T>): T {
  if (!r.ok) {
    throw new ApiError(0, r.error ?? { code: "internal", message: "unknown" });
  }
  return r.data as T;
}

// Dispatch happens at call time, not import time: pywebview injects
// window.pywebview *after* our ESM modules have evaluated. The api object
// must keep the same shape (callable methods) so existing call sites work
// unchanged.
export const api = {
  index: async (): Promise<IndexPayload> => {
    if (isNative()) {
      return (await nativeApi().index()) as IndexPayload;
    }
    if (IS_READONLY) {
      return getJson<IndexPayload>(`${STATIC_BASE}/index.json`);
    }
    return getJson<IndexPayload>("/api/index");
  },

  feature: async (m: string, f: string): Promise<Feature> => {
    if (isNative()) {
      return unwrap<Feature>((await nativeApi().feature(m, f)) as NativeResult<Feature>);
    }
    if (IS_READONLY) {
      return getJson<Feature>(
        `${STATIC_BASE}/prd/${encodeURIComponent(m)}/${encodeURIComponent(f)}.json`,
      );
    }
    return getJson<Feature>(`/api/prd/${m}/${f}`);
  },

  setRuleStatus: async (m: string, f: string, ruleId: string, status: string): Promise<Feature> => {
    if (isNative()) {
      const out = unwrap<Feature>(
        (await nativeApi().set_rule_status(m, f, ruleId, status)) as NativeResult<Feature>,
      );
      noteOwnWrite();
      return out;
    }
    if (IS_READONLY) return readOnlyReject<Feature>();
    return postJson<Feature>(`/api/prd/${m}/${f}/rule/${encodeURIComponent(ruleId)}/status`, {
      status,
    });
  },

  setBugStatus: async (m: string, f: string, bugId: string, status: string): Promise<Feature> => {
    if (isNative()) {
      const out = unwrap<Feature>(
        (await nativeApi().set_bug_status(m, f, bugId, status)) as NativeResult<Feature>,
      );
      noteOwnWrite();
      return out;
    }
    if (IS_READONLY) return readOnlyReject<Feature>();
    return postJson<Feature>(`/api/prd/${m}/${f}/bug/${encodeURIComponent(bugId)}/status`, {
      status,
    });
  },

  resolveFinding: async (m: string, f: string, ruleQid: string): Promise<Feature> => {
    if (isNative()) {
      const out = unwrap<Feature>(
        (await nativeApi().resolve_finding(m, f, ruleQid)) as NativeResult<Feature>,
      );
      noteOwnWrite();
      return out;
    }
    if (IS_READONLY) return readOnlyReject<Feature>();
    return postJson<Feature>(`/api/prd/${m}/${f}/finding/${encodeURIComponent(ruleQid)}/resolve`);
  },
};

export type SseEvent = { type: string; path?: string };
