/** Pure helpers for the RichContent renderer. Kept separate so the component
 *  module exports only a component (keeps react-refresh happy). */

import { IS_READONLY, staticAssetUrl } from "./staticMode";

function encodePath(cleaned: string): string {
  return cleaned
    .split("/")
    .map((p: string) => encodeURIComponent(p))
    .join("/");
}

function nativeAssetUrl(module: string, cleaned: string): string | null {
  const root = typeof window !== "undefined" ? window.__prdAssetRoot : undefined;
  if (!root) return null;
  // file:// URI — `root` is an absolute filesystem path provided by Python.
  return `file://${root}/${encodeURIComponent(module)}/${encodePath(cleaned)}`;
}

/** Rewrite relative <img src="..."> to the dashboard's asset URL.
 *
 *  Native mode (window.pywebview): file://<prd-root>/<module>/<src>.
 *  Static mode (VITE_STATIC_BASE): <BASE>/asset/<module>/<src>.
 *  Live mode: /api/prd-asset/<module>/<feature>/<src>.
 */
export function rewriteImgSrc(html: string, module: string, feature: string): string {
  if (!html.includes("<img")) return html;
  return html.replace(/<img\b([^>]*?)\bsrc="([^"]+)"/gi, (match, pre, src) => {
    if (/^(https?:|data:|file:|\/)/i.test(src)) return match;
    const cleaned = src.replace(/^\.?\//, "");
    const native = nativeAssetUrl(module, cleaned);
    if (native) {
      return `<img${pre}src="${native}"`;
    }
    if (IS_READONLY) {
      return `<img${pre}src="${staticAssetUrl(module, cleaned)}"`;
    }
    return `<img${pre}src="/api/prd-asset/${encodeURIComponent(module)}/${encodeURIComponent(feature)}/${encodePath(cleaned)}"`;
  });
}

/** Parse `prd:<module>/<feature>[#fragment]` into its parts, or null. */
export function parsePrdHref(
  href: string,
): { module: string; feature: string; fragment: string | null } | null {
  if (!href.startsWith("prd:")) return null;
  const rest = href.slice("prd:".length);
  const hashIdx = rest.indexOf("#");
  const refPart = hashIdx === -1 ? rest : rest.slice(0, hashIdx);
  const fragment = hashIdx === -1 ? null : rest.slice(hashIdx + 1);
  const slashIdx = refPart.indexOf("/");
  if (slashIdx === -1) return null;
  const module = refPart.slice(0, slashIdx);
  const feature = refPart.slice(slashIdx + 1);
  if (!module || !feature) return null;
  return { module, feature, fragment };
}
