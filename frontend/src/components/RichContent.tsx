import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { parsePrdHref, rewriteImgSrc } from "@/lib/richContent";

/**
 * Renders a rich-text HTML string from a PRD field (overview, description,
 * rule body, bug current/expected/steps, finding text).
 *
 * - Rewrites relative <img src> to /api/prd-asset/<module>/<feature>/<path>.
 * - Intercepts <a href="prd:<module>/<feature>[#anchor]"> clicks to navigate
 *   in-app via react-router instead of doing a full page load.
 *
 * The HTML is rendered with `dangerouslySetInnerHTML` without sanitization —
 * per the rich-content spec, PRDs are trusted content. See SKILL.md.
 */
export function RichContent({
  html,
  module,
  feature,
  className,
  as: Tag = "div",
}: {
  html: string;
  module: string;
  feature: string;
  className?: string;
  as?: keyof JSX.IntrinsicElements;
}) {
  const navigate = useNavigate();
  const prepared = useMemo(() => rewriteImgSrc(html, module, feature), [html, module, feature]);

  const onClick = useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const anchor = target.closest("a") as HTMLAnchorElement | null;
      if (!anchor) return;
      const href = anchor.getAttribute("href") ?? "";
      if (!href.startsWith("prd:")) return;
      const parsed = parsePrdHref(href);
      if (!parsed) return;
      e.preventDefault();
      const dest = `/p/${parsed.module}/${parsed.feature}${parsed.fragment ? `#${parsed.fragment}` : ""}`;
      navigate(dest);
      if (parsed.fragment) {
        const fragment = parsed.fragment;
        window.requestAnimationFrame(() => {
          const el = document.getElementById(fragment);
          if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
    },
    [navigate],
  );

  if (!html) return null;
  // Tag is a polymorphic intrinsic; cast to a permissive shape for prop typing.
  const Component = Tag as unknown as React.FC<{
    className?: string;
    onClick?: React.MouseEventHandler<HTMLElement>;
    dangerouslySetInnerHTML?: { __html: string };
  }>;
  return (
    <Component
      className={cn("prd-prose", className)}
      onClick={onClick}
      dangerouslySetInnerHTML={{ __html: prepared }}
    />
  );
}
