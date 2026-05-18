import { Feature, IndexPayload } from "./types";
import { noteOwnWrite } from "./useSse";
import { IS_READONLY, STATIC_BASE } from "./lib/staticMode";

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

export const api = IS_READONLY
  ? {
      index: () => getJson<IndexPayload>(`${STATIC_BASE}/index.json`),
      feature: (m: string, f: string) =>
        getJson<Feature>(
          `${STATIC_BASE}/prd/${encodeURIComponent(m)}/${encodeURIComponent(f)}.json`,
        ),
      setRuleStatus: (_m: string, _f: string, _ruleId: string, _status: string) =>
        readOnlyReject<Feature>(),
      setBugStatus: (_m: string, _f: string, _bugId: string, _status: string) =>
        readOnlyReject<Feature>(),
      resolveFinding: (_m: string, _f: string, _ruleQid: string) => readOnlyReject<Feature>(),
    }
  : {
      index: () => getJson<IndexPayload>("/api/index"),
      feature: (m: string, f: string) => getJson<Feature>(`/api/prd/${m}/${f}`),
      setRuleStatus: (m: string, f: string, ruleId: string, status: string) =>
        postJson<Feature>(`/api/prd/${m}/${f}/rule/${encodeURIComponent(ruleId)}/status`, {
          status,
        }),
      setBugStatus: (m: string, f: string, bugId: string, status: string) =>
        postJson<Feature>(`/api/prd/${m}/${f}/bug/${encodeURIComponent(bugId)}/status`, {
          status,
        }),
      resolveFinding: (m: string, f: string, ruleQid: string) =>
        postJson<Feature>(`/api/prd/${m}/${f}/finding/${encodeURIComponent(ruleQid)}/resolve`),
    };

export type SseEvent = { type: string; path?: string };
