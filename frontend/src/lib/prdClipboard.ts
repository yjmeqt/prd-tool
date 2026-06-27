/** Shared helpers for building clipboard text from PRD content — used by the
 *  per-rule copy button and the feature-level "copy for agent" button. */

import { Feature, Requirement, Rule } from "@/types";

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

/** Extract <img src> values from rule HTML and resolve each to a path an agent
 *  can open. Mirrors the viewer's resolution (rewriteImgSrc):
 *  - http(s)/data/absolute srcs are returned unchanged;
 *  - relative srcs resolve against the module dir, prefixed with the absolute
 *    PRD asset root when native mode exposes it, else left module-relative. */
export function extractImagePaths(html: string, module: string): string[] {
  if (!html.includes("<img")) return [];
  const out: string[] = [];
  const re = /<img\b[^>]*?\bsrc="([^"]+)"/gi;
  let m: RegExpExecArray | null;
  const root = typeof window !== "undefined" ? window.__prdAssetRoot : undefined;
  while ((m = re.exec(html)) !== null) {
    const src = m[1];
    if (/^(https?:|data:|file:|\/)/i.test(src)) {
      out.push(src);
      continue;
    }
    const cleaned = src.replace(/^\.?\//, "");
    out.push(root ? `${root}/${module}/${cleaned}` : `${module}/${cleaned}`);
  }
  return out;
}

/** Render a single rule as clipboard markdown lines: a **Rule:** header line
 *  followed by its text, then any image paths and Figma links. Shared by the
 *  per-rule and per-requirement copy builders. */
function ruleLines(rule: Rule, module: string): string[] {
  const parts: string[] = [];
  parts.push(`**Rule:** ${rule.id}${rule.context ? ` (${rule.context})` : ""}`);
  parts.push("");
  parts.push(stripHtmlTags(rule.text));
  const images = extractImagePaths(rule.text, module);
  if (images.length > 0) {
    parts.push("");
    parts.push("**Images:**");
    for (const img of images) parts.push(`- ${img}`);
  }
  if (rule.figma_nodes.length > 0) {
    parts.push("");
    parts.push("**Figma:**");
    for (const fn of rule.figma_nodes) {
      const url = `https://www.figma.com/design/${fn.file}?node-id=${fn.node}`;
      parts.push(`- ${fn.name || "node"}: ${url}`);
    }
  }
  return parts;
}

/** Clipboard text for a single rule, including its feature/requirement context. */
export function buildRulePrompt(
  rule: Rule,
  reqId: string,
  module: string,
  feature: string,
): string {
  return [
    `**Feature:** \`${module}/${feature}\``,
    `**Requirement:** ${reqId}`,
    ...ruleLines(rule, module),
  ].join("\n");
}

/** Clipboard text for an entire requirement: its name/description followed by
 *  every rule, separated by horizontal rules. */
export function buildRequirementPrompt(req: Requirement, module: string, feature: string): string {
  const parts: string[] = [];
  parts.push(`**Feature:** \`${module}/${feature}\``);
  parts.push(`**Requirement:** ${req.id} — ${req.name}`);
  if (req.description) {
    parts.push("");
    parts.push(stripHtmlTags(req.description));
  }
  for (const rule of req.rules) {
    parts.push("");
    parts.push("---");
    parts.push("");
    parts.push(...ruleLines(rule, module));
  }
  return parts.join("\n");
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
