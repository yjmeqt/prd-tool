import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api";
import { Bug } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ArrowRight, Bug as BugIcon, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { RichContent } from "@/components/RichContent";
import { patchIndexStatsFromFeature } from "@/lib/cacheSync";

const BUG_CYCLE: Record<string, string> = {
  Open: "Fix Pending",
  "Fix Pending": "Fixed",
  Fixed: "Open",
};

const STATUS_VARIANT: Record<string, "destructive" | "secondary" | "outline"> = {
  Open: "destructive",
  "Fix Pending": "secondary",
  Fixed: "outline",
};

export function BugCard({ bug, module, feature }: { bug: Bug; module: string; feature: string }) {
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmKind, setConfirmKind] = useState<"fixed" | "reopen" | null>(null);
  // Fixed bugs collapse to a one-line summary by default; Open / Fix-Pending
  // bugs stay expanded so active work is visible at a glance.
  const [expanded, setExpanded] = useState<boolean>(bug.status !== "Fixed");

  const mut = useMutation({
    mutationFn: (status: string) => api.setBugStatus(module, feature, bug.id, status),
    onSuccess: (data) => {
      qc.setQueryData(["feature", module, feature], data);
      patchIndexStatsFromFeature(qc, data);
      qc.invalidateQueries({ queryKey: ["index"] });
    },
    onError: (e: ApiError) => {
      const detail =
        typeof e.detail === "object" && e.detail && "message" in e.detail
          ? (e.detail as { message: string }).message
          : e.message;
      const prefix = e.status === 409 ? "File changed on disk; refreshing. " : "";
      toast.error(`${prefix}Failed to update bug`, { description: detail });
      qc.invalidateQueries({ queryKey: ["feature", module, feature] });
    },
  });

  const next = BUG_CYCLE[bug.status] ?? "Open";

  const onAdvance = () => {
    if (next === "Fixed") {
      setConfirmKind("fixed");
      setConfirmOpen(true);
    } else if (bug.status === "Fixed" && next === "Open") {
      setConfirmKind("reopen");
      setConfirmOpen(true);
    } else {
      mut.mutate(next);
    }
  };

  const confirmAndApply = () => {
    setConfirmOpen(false);
    mut.mutate(next);
  };

  const fixed = bug.status === "Fixed";

  const accent =
    bug.status === "Open"
      ? "border-l-destructive"
      : bug.status === "Fix Pending"
        ? "border-l-[var(--warning)]"
        : "border-l-rule";

  return (
    <>
      <Card
        id={`bug.${bug.id}`}
        className={cn(
          "rounded-none border-l-4 border-y hairline border-r hairline transition-opacity shadow-none bg-card scroll-mt-20",
          accent,
          fixed && "opacity-55",
        )}
      >
        <CardContent className="flex items-start justify-between gap-6 p-5">
          <div className="min-w-0 flex-1 space-y-3">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex w-full items-center gap-3 flex-wrap text-left"
              aria-expanded={expanded}
              aria-label={expanded ? "Collapse bug details" : "Expand bug details"}
            >
              {fixed &&
                (expanded ? (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                ))}
              <BugIcon className="h-3.5 w-3.5 text-muted-foreground" />
              <code className="text-sm font-mono font-medium">{bug.id}</code>
              <Badge
                variant={STATUS_VARIANT[bug.status] ?? "outline"}
                className="text-[10px] uppercase tracking-wider rounded-none font-mono"
              >
                {bug.status}
              </Badge>
              <span className="eyebrow text-muted-foreground">
                filed {bug.date} · {bug.rule}
              </span>
            </button>
            {expanded && (
              <div className="grid grid-cols-[5.5rem_1fr] gap-x-4 gap-y-2 text-[15px] leading-relaxed">
                <span className="eyebrow text-muted-foreground pt-1.5">Current</span>
                <RichContent
                  as="span"
                  html={bug.current}
                  module={module}
                  feature={feature}
                  className="border-l hairline pl-3"
                />
                <span className="eyebrow text-muted-foreground pt-1.5">Expected</span>
                <RichContent
                  as="span"
                  html={bug.expected}
                  module={module}
                  feature={feature}
                  className="border-l hairline pl-3 font-display italic"
                />
                {bug.steps && (
                  <>
                    <span className="eyebrow text-muted-foreground pt-1.5">Steps</span>
                    <RichContent
                      as="span"
                      html={bug.steps}
                      module={module}
                      feature={feature}
                      className="border-l hairline pl-3 whitespace-pre-wrap font-mono text-[13px]"
                    />
                  </>
                )}
              </div>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onAdvance}
            disabled={mut.isPending}
            className="shrink-0 rounded-none eyebrow"
          >
            {next}
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmKind === "fixed" ? "Mark this bug as Fixed?" : "Re-open this fixed bug?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmKind === "fixed"
                ? "The PRD policy requires that you have manually verified the fix works before marking it Fixed."
                : "This will move the bug back to Open. Use this when a previously fixed bug regresses."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmAndApply}>
              {confirmKind === "fixed" ? "Mark Fixed" : "Re-open"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
