import { Badge } from "@/components/ui/badge";
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
    <a href={href} target="_blank" rel="noreferrer" className="no-underline">
      <Badge
        variant="outline"
        className="text-xs gap-1 hover:bg-accent hover:text-accent-foreground transition-colors"
      >
        <span>{name || node}</span>
        <ExternalLink className="h-3 w-3 opacity-60" />
      </Badge>
    </a>
  );
}
