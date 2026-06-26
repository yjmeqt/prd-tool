/** Shared helpers for building clipboard text from PRD content — used by the
 *  per-rule copy button and the feature-level "copy for agent" button. */

import { Feature } from "@/types";

export function stripHtmlTags(html: string): string {
  if (!html) return "";
  return html
    .replace(/<[^>]*>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/\s+\n/g, "\n")
    .trim();
}

/** On-disk path to a feature's source XML. Absolute when native mode exposes
 *  the PRD asset root, else relative to the PRD root. */
export function prdFilePath(module: string, feature: string): string {
  const root = typeof window !== "undefined" ? window.__prdAssetRoot : undefined;
  return root ? `${root}/${module}/${feature}.xml` : `${module}/${feature}.xml`;
}

/** Build a minimal prompt that points another agent at the PRD source. The
 *  PRD file itself holds the requirements, specs, and Figma references, so the
 *  prompt only needs the feature identity and where to read it from. */
export function buildFeaturePrompt(data: Feature): string {
  const path = prdFilePath(data.module, data.feature);
  return [
    `Implement the PRD feature \`${data.ref}\` — "${data.name}".`,
    "",
    `**PRD source:** \`${path}\``,
    `(Figma references and embedded screenshots live alongside it under \`${data.module}/assets/\`.)`,
  ].join("\n");
}
