import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { api } from "@/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const q = useQuery({ queryKey: ["index"], queryFn: api.index });

  return (
    <aside className="w-72 shrink-0 border-r hairline bg-sidebar text-sidebar-foreground">
      <div className="sticky top-0 flex h-screen flex-col">
        {/* Masthead */}
        <div className="px-6 pt-8 pb-6 border-b hairline">
          <div className="eyebrow text-muted-foreground">Established</div>
          <div className="font-display text-3xl leading-none mt-2">
            The
            <br />
            <span className="italic font-medium">Requirement</span>
            <br />
            <span className="text-destructive">Ledger</span>
          </div>
          <div className="mt-4 flex items-center gap-2 eyebrow text-muted-foreground">
            <span className="inline-block h-px w-6 bg-rule" />
            <span>prd-tool</span>
          </div>
        </div>

        <ScrollArea className="flex-1 min-h-0">
          <div className="px-2 py-4">
            {q.isLoading && (
              <div className="px-4 text-sm text-muted-foreground italic">Loading…</div>
            )}
            {q.error && <div className="px-4 text-sm text-destructive">Failed to load index.</div>}
            {q.data && q.data.modules.length === 0 && (
              <div className="px-4 text-sm text-muted-foreground">
                No PRDs found. Create one as{" "}
                <code className="text-xs">prd/&lt;module&gt;/&lt;feature&gt;.xml</code>.
              </div>
            )}
            {q.data?.modules.map((m, mi) => (
              <div key={m.name} className={cn("py-4", mi > 0 && "border-t hairline")}>
                <div className="px-4 mb-2 flex items-baseline justify-between">
                  <span className="eyebrow text-foreground">{m.name}</span>
                  <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                    {String(m.features.length).padStart(2, "0")}
                  </span>
                </div>
                <ul>
                  {m.features.map((f, i) => (
                    <li key={f.ref}>
                      <NavLink
                        to={`/p/${f.module}/${f.feature}`}
                        className={({ isActive }) =>
                          cn(
                            "group flex items-baseline gap-3 px-4 py-1.5 text-[15px] transition-colors relative",
                            isActive
                              ? "text-foreground"
                              : "text-muted-foreground hover:text-foreground",
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <span
                              className={cn(
                                "font-mono text-[10px] tabular-nums text-muted-foreground/70 w-5 shrink-0",
                                isActive && "text-destructive",
                              )}
                            >
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <span
                              className={cn(
                                "font-display leading-tight",
                                isActive && "italic font-medium",
                              )}
                            >
                              {f.name}
                            </span>
                            {isActive && (
                              <span
                                aria-hidden
                                className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 bg-destructive"
                              />
                            )}
                          </>
                        )}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="px-6 py-4 border-t hairline">
          <div className="eyebrow text-muted-foreground/70">All entries · revised on save</div>
        </div>
      </div>
    </aside>
  );
}
