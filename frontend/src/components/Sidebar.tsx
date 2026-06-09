import { useCallback, useEffect, useRef, useState } from "react";
import type React from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { Check, PanelLeft } from "lucide-react";
import { api } from "@/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { isNative, nativeApi } from "@/lib/nativeMode";
import type { IndexFeature } from "@/types";

const COLLAPSED_KEY = "prd-sidebar-collapsed";
const WIDTH_KEY = "prd-sidebar-width";
const MIN_WIDTH = 180;
const MAX_WIDTH = 600;
const DEFAULT_WIDTH = 288;
const COLLAPSED_WIDTH = 48;

/*
 * Animation design:
 *
 * Two layers coexist in the DOM — expanded (full text) and collapsed (dots).
 * Crossfade: expanded fades out first (~120ms), then collapsed fades in
 * (~200ms after a 130ms delay). The width transition runs concurrently over
 * 350ms. The result is a smooth "fold": text dissolves as the panel narrows,
 * dots appear as it settles.
 */
const ANIM_DURATION = 350; // ms — total width transition

function readStoredWidth(): number {
  try {
    const v = parseInt(localStorage.getItem(WIDTH_KEY) ?? "", 10);
    if (v >= MIN_WIDTH && v <= MAX_WIDTH) return v;
  } catch {
    // localStorage unavailable
  }
  return DEFAULT_WIDTH;
}

function onFeatureNavClick(ref: string) {
  return (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (isNative() && (e.metaKey || e.ctrlKey || e.button === 1)) {
      e.preventDefault();
      void nativeApi().open_window(ref);
    }
  };
}

export function Sidebar() {
  const q = useQuery({ queryKey: ["index"], queryFn: api.index });
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [width, setWidth] = useState(readStoredWidth);
  const [dragging, setDragging] = useState(false);
  const draggingRef = useRef(false);
  const asideRef = useRef<HTMLElement>(null);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        // localStorage unavailable
      }
      return next;
    });
  }, []);

  // Keyboard shortcut: Cmd+B / Ctrl+B toggles the sidebar
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggle]);

  // ---- Resize handle ----
  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = true;
      setDragging(true);
      const startX = e.clientX;
      const startWidth = asideRef.current?.offsetWidth ?? width;

      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";

      function onMouseMove(ev: MouseEvent) {
        if (!draggingRef.current) return;
        const delta = ev.clientX - startX;
        const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta));
        setWidth(next);
      }

      function onMouseUp() {
        draggingRef.current = false;
        setDragging(false);
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
        try {
          const finalWidth = asideRef.current?.offsetWidth;
          if (finalWidth && finalWidth >= MIN_WIDTH && finalWidth <= MAX_WIDTH) {
            localStorage.setItem(WIDTH_KEY, String(finalWidth));
          }
        } catch {
          // localStorage unavailable
        }
      }

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    },
    [width],
  );

  const computedWidth = collapsed ? COLLAPSED_WIDTH : width;

  return (
    <aside
      ref={asideRef}
      className={cn(
        "shrink-0 border-r hairline bg-sidebar text-sidebar-foreground relative",
        !dragging && "transition-[width] ease-in-out",
      )}
      style={{ width: computedWidth, transitionDuration: `${ANIM_DURATION}ms` }}
    >
      <div className="sticky top-0 flex h-screen flex-col overflow-hidden">
        {/* Toggle button */}
        <div
          className={cn(
            "absolute z-20 flex transition-all",
            collapsed ? "top-3 right-0.5" : "top-3 right-2",
          )}
          style={{ transitionDuration: `${ANIM_DURATION}ms` }}
        >
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <button
                onClick={toggle}
                className={cn(
                  "flex items-center justify-center rounded-md border hairline bg-sidebar/90 backdrop-blur text-muted-foreground hover:text-foreground hover:bg-accent transition-colors",
                  collapsed ? "w-8 h-8" : "w-7 h-7",
                )}
                aria-label={collapsed ? "Expand sidebar (⌘B)" : "Collapse sidebar (⌘B)"}
              >
                <PanelLeft
                  className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")}
                  style={{ transitionDuration: `${ANIM_DURATION}ms` }}
                />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {collapsed ? "Expand sidebar" : "Collapse sidebar"}
              <span className="ml-2 font-mono text-[10px] text-muted-foreground">⌘B</span>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* ── Expanded layer ── */}
        <div
          aria-hidden={collapsed}
          className={cn(
            "flex flex-col h-full transition-opacity",
            collapsed ? "opacity-0 pointer-events-none" : "opacity-100",
          )}
          style={{
            transitionDuration: collapsed ? "120ms" : "200ms",
            transitionDelay: collapsed ? "0ms" : "130ms",
          }}
        >
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
              {q.error && (
                <div className="px-4 text-sm text-destructive">Failed to load index.</div>
              )}
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
                          onClick={onFeatureNavClick(`${f.module}/${f.feature}`)}
                          className={({ isActive }) =>
                            cn(
                              "group flex items-center gap-3 px-4 py-1.5 text-[15px] transition-colors relative",
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
                                  "flex-1 min-w-0 truncate font-display leading-tight",
                                  isActive && "italic font-medium",
                                )}
                                title={f.name}
                              >
                                {f.name}
                              </span>
                              <FeatureIndicators feature={f} />
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

          {/* Footer */}
          <div className="px-6 py-4 border-t hairline">
            <div className="eyebrow text-muted-foreground/70">All entries · revised on save</div>
          </div>
        </div>

        {/* ── Collapsed layer ── */}
        <div
          aria-hidden={!collapsed}
          className={cn(
            "absolute inset-0 flex flex-col transition-opacity",
            collapsed ? "opacity-100" : "opacity-0 pointer-events-none",
          )}
          style={{
            transitionDuration: collapsed ? "200ms" : "100ms",
            transitionDelay: collapsed ? "150ms" : "0ms",
          }}
        >
          {/* Masthead dot */}
          <div className="px-2 pt-10 pb-3 border-b hairline flex flex-col items-center gap-2">
            <span className="font-display text-lg italic leading-none text-destructive">R</span>
            <span className="font-mono text-[9px] text-muted-foreground/60">prd</span>
          </div>

          <ScrollArea className="flex-1 min-h-0">
            <div className="px-1 py-4">
              {q.data?.modules.map((m, mi) => (
                <div
                  key={m.name}
                  className={cn(
                    "py-2 flex flex-col items-center gap-1.5",
                    mi > 0 && "border-t hairline",
                  )}
                >
                  <span
                    className="font-mono text-[10px] text-muted-foreground tabular-nums leading-none"
                    title={m.name}
                  >
                    {m.name.slice(0, 2).toUpperCase()}
                  </span>
                  {m.features.map((f) => (
                    <Tooltip key={f.ref} delayDuration={300}>
                      <TooltipTrigger asChild>
                        <NavLink
                          to={`/p/${f.module}/${f.feature}`}
                          onClick={onFeatureNavClick(`${f.module}/${f.feature}`)}
                          className={({ isActive }) =>
                            cn(
                              "block w-2 h-2 rounded-full transition-colors",
                              isActive
                                ? "bg-destructive"
                                : "bg-muted-foreground/25 hover:bg-muted-foreground/50",
                            )
                          }
                        />
                      </TooltipTrigger>
                      <TooltipContent side="right" sideOffset={8}>
                        <span className="font-display text-xs">{f.name}</span>
                      </TooltipContent>
                    </Tooltip>
                  ))}
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Footer dot */}
          <div className="px-2 py-3 text-center border-t hairline">
            <span
              className="font-mono text-[9px] text-muted-foreground/50 cursor-pointer hover:text-muted-foreground"
              onClick={toggle}
            >
              ⌘B
            </span>
          </div>
        </div>
      </div>

      {/* Resize handle — only visible when expanded */}
      <div
        onMouseDown={onMouseDown}
        className={cn(
          "absolute top-0 right-0 h-full w-[5px] cursor-col-resize z-20",
          "hover:bg-destructive/20",
          "after:absolute after:inset-y-0 after:left-1/2 after:-translate-x-px after:w-px after:bg-transparent hover:after:bg-destructive/30",
          collapsed && "hidden",
        )}
      />
    </aside>
  );
}

function FeatureIndicators({ feature }: { feature: IndexFeature }) {
  const { rules_done, rules_total, bugs_active } = feature.stats;
  const isComplete = rules_total > 0 && rules_done === rules_total && bugs_active === 0;

  if (isComplete) {
    return (
      <span
        aria-label="All work complete"
        title="All rules done, no active bugs"
        className="shrink-0 inline-flex items-center text-muted-foreground/60"
      >
        <Check className="h-3 w-3" />
      </span>
    );
  }

  return (
    <span className="shrink-0 inline-flex items-center gap-1.5">
      {rules_total > 0 && (
        <span
          className="font-mono text-[10px] tabular-nums text-muted-foreground/70"
          title={`${rules_done} of ${rules_total} rules done`}
        >
          {rules_done}/{rules_total}
        </span>
      )}
      {bugs_active > 0 && (
        <span
          className="font-mono text-[10px] tabular-nums px-1 py-px rounded-sm bg-destructive/10 text-destructive"
          title={`${bugs_active} active bug${bugs_active === 1 ? "" : "s"}`}
        >
          {bugs_active}
        </span>
      )}
    </span>
  );
}
