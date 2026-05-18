/** Read-only static mode (no Python backend), enabled by VITE_STATIC_BASE.
 *
 *  VITE_STATIC_BASE points at a directory written by `prd export-json`,
 *  laid out as:
 *    <BASE>/index.json
 *    <BASE>/prd/<module>/<feature>.json
 *    <BASE>/asset/<module>/<asset_path>
 *
 *  When unset, the dashboard talks to the live FastAPI app at /api/*.
 */

function readBase(): string | null {
  const raw = import.meta.env.VITE_STATIC_BASE ?? "";
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
}

export const STATIC_BASE: string | null = readBase();
export const IS_READONLY: boolean = STATIC_BASE !== null;

export function staticAssetUrl(module: string, assetPath: string): string {
  const encoded = assetPath
    .split("/")
    .map((p) => encodeURIComponent(p))
    .join("/");
  return `${STATIC_BASE}/asset/${encodeURIComponent(module)}/${encoded}`;
}
