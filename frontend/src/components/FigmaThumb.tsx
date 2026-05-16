import { ExternalLink } from "lucide-react";

export function FigmaThumb({
  name,
  fileKey,
  node,
}: {
  name: string;
  fileKey: string;
  node: string;
}) {
  const nodeParam = node.includes(":") ? node.replace(/:/g, "-") : node;
  const href = `https://www.figma.com/design/${fileKey}/?node-id=${encodeURIComponent(nodeParam)}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex w-fit items-center gap-1.5 rounded-full bg-violet-600 px-2.5 py-1 text-xs font-semibold text-white no-underline shadow-sm ring-1 ring-violet-700/40 transition-colors hover:bg-violet-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 dark:bg-violet-500 dark:ring-violet-300/30 dark:hover:bg-violet-400"
    >
      <FigmaGlyph className="h-3 w-3 shrink-0" />
      <span className="opacity-90">Figma</span>
      <span aria-hidden className="opacity-50">
        ·
      </span>
      <span className="truncate max-w-[18ch]">{name || node}</span>
      <ExternalLink className="h-3 w-3 shrink-0 opacity-80" />
    </a>
  );
}

function FigmaGlyph({ className }: { className?: string }) {
  // Simplified Figma logo mark
  return (
    <svg className={className} viewBox="0 0 38 57" aria-hidden fill="currentColor">
      <path d="M19 28.5a9.5 9.5 0 1 1 0 19 9.5 9.5 0 0 1 0-19Z" opacity=".95" />
      <path d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 1 1-19 0Z" opacity=".8" />
      <path d="M19 0v19h9.5a9.5 9.5 0 1 0 0-19H19Z" opacity=".85" />
      <path d="M0 9.5A9.5 9.5 0 0 1 9.5 0H19v19H9.5A9.5 9.5 0 0 1 0 9.5Z" opacity=".75" />
      <path d="M0 28.5A9.5 9.5 0 0 1 9.5 19H19v19H9.5A9.5 9.5 0 0 1 0 28.5Z" opacity=".9" />
    </svg>
  );
}
