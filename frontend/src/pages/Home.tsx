import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api";
import { IndexFeature } from "@/types";
import { useDocumentTitle } from "@/useDocumentTitle";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { UnfinishedToggle } from "@/components/UnfinishedToggle";
import { useUnfinishedOnly } from "@/useUnfinishedOnly";

type SortKey = "module" | "name" | "rules" | "bugs" | "ui";

function SortIcon({ active, dir }: { active: boolean; dir: 1 | -1 }) {
  if (!active) return <ArrowUpDown className="h-3 w-3 opacity-30" />;
  return dir === 1 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />;
}

export function HomePage() {
  useDocumentTitle([]);
  const q = useQuery({ queryKey: ["index"], queryFn: api.index });
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({
    key: "bugs",
    dir: -1,
  });
  const [unfinishedOnly] = useUnfinishedOnly();

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: -s.dir as 1 | -1 } : { key, dir: -1 }));

  const rows = useMemo<IndexFeature[]>(() => {
    const flat: IndexFeature[] = [];
    q.data?.modules.forEach((m) =>
      m.features.forEach((f) => {
        if (unfinishedOnly) {
          const done =
            f.stats.rules_total > 0 &&
            f.stats.rules_done === f.stats.rules_total &&
            f.stats.bugs_active === 0;
          if (done) return;
        }
        flat.push(f);
      }),
    );
    flat.sort((a, b) => {
      const sign = sort.dir;
      switch (sort.key) {
        case "module":
          return sign * a.module.localeCompare(b.module);
        case "name":
          return sign * a.name.localeCompare(b.name);
        case "rules": {
          const ar = a.stats.rules_total - a.stats.rules_done;
          const br = b.stats.rules_total - b.stats.rules_done;
          return sign * (ar - br);
        }
        case "bugs":
          return sign * (a.stats.bugs_open - b.stats.bugs_open);
        case "ui":
          return sign * (a.stats.ui_total - b.stats.ui_total);
      }
    });
    return flat;
  }, [q.data, sort, unfinishedOnly]);

  const totals = useMemo(() => {
    return rows.reduce(
      (acc, f) => {
        acc.rules_total += f.stats.rules_total;
        acc.rules_done += f.stats.rules_done;
        acc.bugs_open += f.stats.bugs_open;
        acc.features += 1;
        return acc;
      },
      { rules_total: 0, rules_done: 0, bugs_open: 0, features: 0 },
    );
  }, [rows]);

  if (q.isLoading)
    return <div className="text-sm text-muted-foreground italic py-12">Loading PRDs…</div>;
  if (q.error)
    return (
      <div className="border-l-2 border-destructive bg-destructive/5 px-4 py-3 text-sm text-destructive">
        Failed to load PRD index.
      </div>
    );
  if (!q.data || rows.length === 0)
    return (
      <div className="text-sm text-muted-foreground py-12">
        No PRDs in this repo yet. Create one under <code className="text-xs">prd/</code>.
      </div>
    );

  const pctOverall =
    totals.rules_total === 0 ? 0 : Math.round((totals.rules_done / totals.rules_total) * 100);

  return (
    <div>
      {/* Banner */}
      <header className="mb-12 border-b-2 border-foreground pb-8">
        <div className="eyebrow text-muted-foreground rise rise-1">
          The Index · {totals.features} entries on file
        </div>
        <h1 className="font-display text-[88px] leading-[0.88] tracking-[-0.04em] mt-3 rise rise-2">
          Product
          <br />
          <span className="italic font-normal">Requirements</span>
        </h1>
        <p className="font-display italic text-xl text-muted-foreground mt-6 max-w-xl rise rise-3">
          A standing record of every PRD in this repository — sorted by what wants your attention.
        </p>

        {/* Ledger summary row */}
        <div className="mt-10 grid grid-cols-3 gap-px bg-rule border hairline rise rise-4">
          <Stat
            label="Rules complete"
            value={`${totals.rules_done}/${totals.rules_total}`}
            sub={`${pctOverall}%`}
          />
          <Stat
            label="Open bugs"
            value={String(totals.bugs_open)}
            sub={totals.bugs_open === 0 ? "clean" : "outstanding"}
            tone={totals.bugs_open > 0 ? "destructive" : undefined}
          />
          <Stat label="Features" value={String(totals.features)} sub="documented" />
        </div>
      </header>

      {/* Listing */}
      <section className="rise rise-4">
        <div className="flex items-baseline justify-between mb-4 gap-4">
          <h2 className="eyebrow">The Listing</h2>
          <div className="flex items-center gap-3">
            <UnfinishedToggle />
            <span className="eyebrow text-muted-foreground">
              {rows.length} {rows.length === 1 ? "entry" : "entries"}
            </span>
          </div>
        </div>

        <div className="border-y-2 border-foreground">
          <table className="w-full text-[15px]">
            <thead>
              <tr className="border-b hairline">
                <Th
                  onClick={() => toggle("module")}
                  active={sort.key === "module"}
                  dir={sort.dir}
                  className="w-[18%]"
                >
                  Module
                </Th>
                <Th onClick={() => toggle("name")} active={sort.key === "name"} dir={sort.dir}>
                  Feature
                </Th>
                <Th
                  onClick={() => toggle("rules")}
                  active={sort.key === "rules"}
                  dir={sort.dir}
                  align="right"
                  className="w-[18%]"
                >
                  Rules
                </Th>
                <Th
                  onClick={() => toggle("bugs")}
                  active={sort.key === "bugs"}
                  dir={sort.dir}
                  align="right"
                  className="w-[12%]"
                >
                  Bugs
                </Th>
                <Th
                  onClick={() => toggle("ui")}
                  active={sort.key === "ui"}
                  dir={sort.dir}
                  align="right"
                  className="w-[12%]"
                >
                  UI
                </Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f, i) => {
                const pct =
                  f.stats.rules_total === 0
                    ? 0
                    : Math.round((f.stats.rules_done / f.stats.rules_total) * 100);
                return (
                  <tr
                    key={f.ref}
                    className={cn(
                      "border-b hairline last:border-b-0 group transition-colors",
                      "hover:bg-accent/40",
                    )}
                  >
                    <td className="px-2 py-4 align-baseline">
                      <span className="eyebrow text-muted-foreground">{f.module}</span>
                    </td>
                    <td className="px-2 py-4 align-baseline">
                      <Link
                        to={`/p/${f.module}/${f.feature}`}
                        className="font-display text-xl leading-tight tracking-tight hover:italic transition-all inline-flex items-baseline gap-3"
                      >
                        <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70 not-italic">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="group-hover:text-destructive transition-colors">
                          {f.name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-2 py-4 text-right align-baseline">
                      <div className="inline-flex items-center gap-3">
                        <span className="font-mono text-xs tabular-nums text-muted-foreground">
                          {f.stats.rules_done}/{f.stats.rules_total}
                        </span>
                        <div className="w-16 h-px bg-rule relative">
                          <div
                            className="absolute inset-y-0 left-0 -top-px h-0.5 bg-foreground"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-2 py-4 text-right align-baseline">
                      {f.stats.bugs_open === 0 ? (
                        <span className="font-mono text-xs text-muted-foreground/60">—</span>
                      ) : (
                        <span className="font-display text-xl tabular-nums text-destructive">
                          {f.stats.bugs_open}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-4 text-right align-baseline">
                      <span className="font-mono text-xs tabular-nums text-muted-foreground">
                        {f.stats.ui_total === 0
                          ? "—"
                          : `${f.stats.ui_reviewed}/${f.stats.ui_total}`}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-3 eyebrow text-muted-foreground/70 text-right">— end of listing —</div>
      </section>
    </div>
  );
}

function Th({
  children,
  onClick,
  active,
  dir,
  align = "left",
  className,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  dir: 1 | -1;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <th
      onClick={onClick}
      className={cn(
        "eyebrow text-muted-foreground py-3 px-2 cursor-pointer select-none hover:text-foreground transition-colors",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      <span
        className={cn("inline-flex items-center gap-1.5", align === "right" && "flex-row-reverse")}
      >
        {children}
        <SortIcon active={active} dir={dir} />
      </span>
    </th>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "destructive";
}) {
  return (
    <div className="bg-background px-6 py-5">
      <div className="eyebrow text-muted-foreground">{label}</div>
      <div className={cn("numeral text-5xl mt-2", tone === "destructive" && "text-destructive")}>
        {value}
      </div>
      {sub && <div className="font-display italic text-sm text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}
