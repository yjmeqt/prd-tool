import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "@/api";
import { RuleCard } from "@/components/RuleCard";
import { BugCard } from "@/components/BugCard";
import { UiReviewBlock } from "@/components/UiReviewBlock";
import { RichContent } from "@/components/RichContent";
import { useDocumentTitle } from "@/useDocumentTitle";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const BUG_ORDER: Record<string, number> = { Open: 0, "Fix Pending": 1, Fixed: 2 };

export function FeaturePage() {
  const { module, feature } = useParams();
  const q = useQuery({
    queryKey: ["feature", module, feature],
    queryFn: () => api.feature(module!, feature!),
    enabled: Boolean(module && feature),
  });
  useDocumentTitle([q.data?.name ?? feature]);

  if (q.isLoading)
    return <div className="text-sm text-muted-foreground italic py-12">Loading…</div>;
  if (q.error)
    return (
      <div className="border-l-2 border-destructive bg-destructive/5 px-4 py-3 text-sm text-destructive">
        Failed to load this PRD.
      </div>
    );
  const data = q.data;
  if (!data) return null;
  if (data.parse_error) {
    return (
      <div className="flex items-start gap-3 border-l-2 border-destructive bg-destructive/5 p-4 text-sm">
        <AlertCircle className="h-4 w-4 mt-0.5 text-destructive shrink-0" />
        <div>
          <div className="font-medium text-destructive">Could not parse {data.ref}</div>
          <div className="text-muted-foreground mt-0.5">{data.parse_error}</div>
        </div>
      </div>
    );
  }

  const sortedBugs = [...data.bugs].sort(
    (a, b) => (BUG_ORDER[a.status] ?? 9) - (BUG_ORDER[b.status] ?? 9),
  );

  const pct =
    data.stats.rules_total === 0
      ? 0
      : Math.round((data.stats.rules_done / data.stats.rules_total) * 100);

  return (
    <div>
      {/* Folio header */}
      <header className="mb-14 rise rise-1">
        <div className="eyebrow text-muted-foreground flex items-center gap-3">
          <span>{data.module}</span>
          <span className="text-rule">/</span>
          <span className="font-mono">{data.ref}</span>
        </div>
        <h1 className="font-display text-6xl leading-[0.95] tracking-tight mt-3">{data.name}</h1>
        {data.overview && (
          <RichContent
            html={data.overview}
            module={data.module}
            feature={data.feature}
            className="mt-6 font-display text-xl leading-relaxed text-foreground/80 max-w-2xl italic"
          />
        )}

        {/* Ledger strip */}
        <div className="mt-10 border-y-2 border-foreground py-6 grid grid-cols-4 gap-x-6 gap-y-2 rise rise-2">
          <StatCell
            label="Rules"
            big={`${data.stats.rules_done}/${data.stats.rules_total}`}
            sub={`${pct}% complete`}
          />
          <StatCell
            label="Open bugs"
            big={String(data.stats.bugs_open)}
            sub={data.stats.bugs_open === 0 ? "clean" : "outstanding"}
            tone={data.stats.bugs_open > 0 ? "destructive" : undefined}
          />
          <StatCell
            label="UI review"
            big={
              data.stats.ui_total === 0 ? "—" : `${data.stats.ui_reviewed}/${data.stats.ui_total}`
            }
            sub={data.stats.ui_total === 0 ? "not reviewed" : "verified"}
          />
          <StatCell
            label="Platforms"
            big={String(data.implementations.length)}
            sub={data.implementations.length === 1 ? "specification" : "specifications"}
          />
        </div>
      </header>

      {/* Implementations */}
      {data.implementations.length > 0 && (
        <section className="mb-14 rise rise-3">
          <SectionHead eyebrow="The Specifications" title="Implementations" />
          <div className="border-y hairline divide-y divide-[var(--rule)]">
            {data.implementations.map((impl, i) => (
              <div key={i} className="flex items-baseline gap-6 py-3 px-1">
                <span className="eyebrow text-muted-foreground w-20 shrink-0">{impl.platform}</span>
                {!impl.spec || impl.spec === "TBD" ? (
                  <span className="font-display italic text-muted-foreground">
                    to be determined
                  </span>
                ) : (
                  <code className="text-sm text-foreground/70 break-all">{impl.spec}</code>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Requirements */}
      <section className="mb-14 rise rise-3">
        <SectionHead eyebrow="The Articles" title="Requirements" count={data.requirements.length} />
        <div className="space-y-12">
          {data.requirements.map((req, idx) => (
            <article key={req.id} id={req.id} className="relative pl-14 scroll-mt-20">
              {/* Ledger gutter */}
              <div className="absolute left-0 top-0 bottom-0 w-10 flex flex-col items-start">
                <div className="font-display text-4xl leading-none text-destructive italic">
                  {req.id}
                </div>
                <div className="mt-2 w-px flex-1 bg-rule" />
                <div className="font-mono text-[10px] tabular-nums text-muted-foreground/60 mt-2">
                  {String(idx + 1).padStart(2, "0")}/
                  {String(data.requirements.length).padStart(2, "0")}
                </div>
              </div>

              <header className="mb-4">
                <h3 className="font-display text-3xl tracking-tight leading-tight">{req.name}</h3>
                {req.description && (
                  <RichContent
                    html={req.description}
                    module={data.module}
                    feature={data.feature}
                    className="mt-2 text-muted-foreground leading-relaxed max-w-2xl"
                  />
                )}
              </header>

              <div className="border-t hairline">
                {req.rules.map((rule) => (
                  <RuleCard
                    key={rule.id}
                    rule={rule}
                    reqId={req.id}
                    module={data.module}
                    feature={data.feature}
                  />
                ))}
              </div>
              {req.ui_reviews.map((ur, i) => (
                <UiReviewBlock key={i} review={ur} module={data.module} feature={data.feature} />
              ))}
            </article>
          ))}
        </div>
      </section>

      {/* Bugs */}
      {sortedBugs.length > 0 && (
        <section className="mb-14 rise rise-4">
          <SectionHead eyebrow="The Errata" title="Bugs" count={sortedBugs.length} />
          <div className="space-y-4">
            {sortedBugs.map((bug) => (
              <BugCard key={bug.id} bug={bug} module={data.module} feature={data.feature} />
            ))}
          </div>
        </section>
      )}

      <div className="eyebrow text-muted-foreground/60 text-center pt-8 border-t hairline">
        — fin —
      </div>
    </div>
  );
}

function SectionHead({
  eyebrow,
  title,
  count,
}: {
  eyebrow: string;
  title: string;
  count?: number;
}) {
  return (
    <div className="mb-6 flex items-baseline justify-between border-b hairline pb-3">
      <div>
        <div className="eyebrow text-muted-foreground">{eyebrow}</div>
        <h2 className="font-display text-2xl italic mt-1">{title}</h2>
      </div>
      {count !== undefined && (
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          № {String(count).padStart(2, "0")}
        </span>
      )}
    </div>
  );
}

function StatCell({
  label,
  big,
  sub,
  tone,
}: {
  label: string;
  big: string;
  sub: string;
  tone?: "destructive";
}) {
  return (
    <div>
      <div className="eyebrow text-muted-foreground">{label}</div>
      <div className={cn("numeral text-5xl mt-1", tone === "destructive" && "text-destructive")}>
        {big}
      </div>
      <div className="font-display italic text-sm text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}
