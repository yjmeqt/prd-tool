import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api";
import { Rule } from "@/types";
import { FigmaThumb } from "@/components/FigmaThumb";
import { RichContent } from "@/components/RichContent";
import { patchIndexStatsFromFeature } from "@/lib/cacheSync";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Check, X, CircleDashed } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const RULE_CYCLE: Record<string, string> = { "❌": "⚠️", "⚠️": "✅", "✅": "❌" };

function StatusGlyph({ status }: { status: string }) {
  if (status === "✅") return <Check className="h-3.5 w-3.5" style={{ color: "var(--success)" }} />;
  if (status === "⚠️")
    return <CircleDashed className="h-3.5 w-3.5" style={{ color: "var(--warning)" }} />;
  return <X className="h-3.5 w-3.5 text-destructive" />;
}

const STATUS_LABEL: Record<string, string> = {
  "✅": "Implemented · click to mark not done",
  "⚠️": "Partial · click to mark done",
  "❌": "Not implemented · click to mark partial",
};

export function RuleCard({
  rule,
  reqId,
  module,
  feature,
}: {
  rule: Rule;
  reqId: string;
  module: string;
  feature: string;
}) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: (status: string) => api.setRuleStatus(module, feature, rule.id, status),
    onSuccess: (data) => {
      qc.setQueryData(["feature", module, feature], data);
      patchIndexStatsFromFeature(qc, data);
      qc.invalidateQueries({ queryKey: ["index"] });
    },
    onError: (e: ApiError) => {
      const msg =
        typeof e.detail === "object" && e.detail && "message" in e.detail
          ? (e.detail as { message: string }).message
          : e.message;
      const prefix = e.status === 409 ? "File changed on disk; refreshing. " : "";
      toast.error(`${prefix}Failed to update rule`, { description: msg });
      qc.invalidateQueries({ queryKey: ["feature", module, feature] });
    },
  });

  const onClick = () => mut.mutate(RULE_CYCLE[rule.status] ?? "❌");
  const dimmed = rule.status === "✅";

  return (
    <div
      id={`${reqId}.${rule.id}`}
      className={cn(
        "flex items-start gap-4 py-3 border-b hairline last:border-b-0 transition-colors hover:bg-accent/20 scroll-mt-20",
        dimmed && "opacity-60",
      )}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0 rounded-none border hairline mt-0.5"
            onClick={onClick}
            disabled={mut.isPending}
            aria-label={STATUS_LABEL[rule.status] ?? rule.status}
          >
            <StatusGlyph status={rule.status} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{STATUS_LABEL[rule.status] ?? rule.status}</TooltipContent>
      </Tooltip>

      <div className="flex-1 min-w-0 text-[15px] leading-relaxed">
        <code className="text-[11px] text-muted-foreground mr-2 font-mono uppercase tracking-wider">
          {rule.id}
        </code>
        {rule.context && (
          <span className="font-display italic text-muted-foreground mr-1">({rule.context})</span>
        )}
        <RichContent
          as="span"
          html={rule.text}
          module={module}
          feature={feature}
          className={cn(
            "inline align-baseline",
            dimmed && "text-muted-foreground line-through decoration-rule",
          )}
        />
        {rule.figma_nodes.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {rule.figma_nodes.map((fn, i) => (
              <FigmaThumb key={i} name={fn.name} fileKey={fn.file} node={fn.node} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
