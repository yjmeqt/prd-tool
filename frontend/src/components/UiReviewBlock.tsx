import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api";
import { UiReview } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Eye, Check } from "lucide-react";
import { toast } from "sonner";
import { RichContent } from "@/components/RichContent";
import { patchIndexStatsFromFeature } from "@/lib/cacheSync";

function detailMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail;
    if (typeof d === "object" && d && "message" in d)
      return String((d as { message: unknown }).message);
    return String(d);
  }
  return e instanceof Error ? e.message : String(e);
}

const STATUS: Record<string, { label: string; variant: "destructive" | "secondary" | "outline" }> =
  {
    "✅": { label: "Verified", variant: "outline" },
    "❌": { label: "Findings open", variant: "destructive" },
    "⚠️": { label: "Partially resolved", variant: "secondary" },
  };

export function UiReviewBlock({
  review,
  module,
  feature,
}: {
  review: UiReview;
  module: string;
  feature: string;
}) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: (ruleQid: string) => api.resolveFinding(module, feature, ruleQid),
    onSuccess: (data) => {
      qc.setQueryData(["feature", module, feature], data);
      patchIndexStatsFromFeature(qc, data);
      qc.invalidateQueries({ queryKey: ["index"] });
    },
    onError: (e) => {
      toast.error("Failed to resolve finding", { description: detailMessage(e) });
      qc.invalidateQueries({ queryKey: ["feature", module, feature] });
    },
  });
  const s = STATUS[review.status] ?? { label: review.status, variant: "outline" as const };

  return (
    <div className="mt-5 border-t-2 border-foreground/80 pt-3">
      <div className="flex items-center gap-3 text-sm">
        <Eye className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="eyebrow">UI Review</span>
        <Badge
          variant={s.variant}
          className="text-[10px] rounded-none uppercase tracking-wider font-mono"
        >
          {s.label}
        </Badge>
        <span className="eyebrow text-muted-foreground">{review.date}</span>
      </div>
      {review.findings.length === 0 && (
        <p className="mt-2 text-sm text-muted-foreground">No outstanding findings.</p>
      )}
      {review.findings.length > 0 && (
        <div className="mt-2 divide-y">
          {review.findings.map((f, i) => (
            <div key={i} className="flex items-start gap-2 py-2 text-sm">
              <code className="text-xs text-muted-foreground font-mono shrink-0 mt-0.5">
                {f.rule}
              </code>
              <RichContent
                as="span"
                html={f.text}
                module={module}
                feature={feature}
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => mut.mutate(f.rule)}
                disabled={mut.isPending}
                className="h-7 px-2 text-xs"
              >
                <Check className="h-3.5 w-3.5 mr-1" /> Resolve
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
