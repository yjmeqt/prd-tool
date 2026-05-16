/** Pure helpers for the RichContent renderer. Kept separate so the component
 *  module exports only a component (keeps react-refresh happy). */

/** Rewrite relative <img src="..."> to /api/prd-asset/<module>/<feature>/<src>. */
export function rewriteImgSrc(html: string, module: string, feature: string): string {
  if (!html.includes("<img")) return html;
  return html.replace(/<img\b([^>]*?)\bsrc="([^"]+)"/gi, (match, pre, src) => {
    if (/^(https?:|data:|\/)/i.test(src)) return match;
    const cleaned = src.replace(/^\.?\//, "");
    const encoded = cleaned
      .split("/")
      .map((p: string) => encodeURIComponent(p))
      .join("/");
    return `<img${pre}src="/api/prd-asset/${encodeURIComponent(module)}/${encodeURIComponent(feature)}/${encoded}"`;
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
