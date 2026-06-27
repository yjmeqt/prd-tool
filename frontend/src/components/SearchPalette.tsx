import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  CornerDownLeft,
  RefreshCw,
  Loader2,
  FileText,
  Image as ImageIcon,
} from "lucide-react";
import { api } from "@/api";
import { cn } from "@/lib/utils";
import { IS_READONLY } from "@/lib/staticMode";
import { assetUrl } from "@/lib/richContent";
import type { SearchResult, SearchStatus } from "@/types";
import { toast } from "sonner";

/** Scroll a rule/requirement/bug into view by its DOM id, retrying across
 *  frames while the feature page mounts and react-query resolves. */
function scrollToAnchor(anchor: string) {
  if (!anchor) return;
  let tries = 0;
  const tick = () => {
    const el = document.getElementById(anchor);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("search-flash");
      window.setTimeout(() => el.classList.remove("search-flash"), 1600);
      return;
    }
    if (tries++ < 90) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** Split text on case-insensitive query matches and bold the matched runs. */
function highlight(text: string, query: string) {
  const terms = Array.from(
    new Set([query.trim(), ...(query.toLowerCase().match(/[a-z0-9]+/g) || [])].filter(Boolean)),
  );
  if (terms.length === 0) return text;
  const escaped = terms
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .sort((a, b) => b.length - a.length);
  const re = new RegExp(`(${escaped.join("|")})`, "ig");
  const parts = text.split(re);
  return parts.map((p, i) =>
    re.test(p) ? (
      <mark
        key={i}
        className="bg-transparent text-foreground font-medium underline decoration-destructive/50"
      >
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

function timeAgo(ts: number | null): string {
  if (!ts) return "never";
  const secs = Date.now() / 1000 - ts;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

const KIND_LABEL: Record<string, string> = {
  rule: "Rule",
  requirement: "Req",
  bug: "Bug",
  overview: "Overview",
  finding: "Finding",
  image: "Image",
};

export function SearchPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [visual, setVisual] = useState<SearchResult[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<SearchStatus | null>(null);
  const [needsIndex, setNeedsIndex] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [nonce, setNonce] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Global ⌘K / Ctrl+K toggle, plus an event other UI (the masthead button)
  // can dispatch to open the palette.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("prd:open-search", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("prd:open-search", onOpen);
    };
  }, []);

  // Load index status whenever the palette opens.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    api
      .searchStatus()
      .then((s) => {
        setStatus(s);
        setNeedsIndex(!s.exists);
      })
      .catch(() => undefined);
  }, [open]);

  // Debounced search as the query (or post-reindex nonce) changes. All state
  // updates happen inside the timeout callback so they're never synchronous
  // within the effect body.
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    let cancelled = false;
    const id = window.setTimeout(() => {
      if (!q) {
        setResults([]);
        setVisual([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      api
        .search(q, 30)
        .then((r) => {
          if (cancelled) return;
          setResults(r.results);
          setVisual(r.visual ?? []);
          setNeedsIndex(r.needs_index);
          setActive(0);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
    };
  }, [query, open, nonce]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setVisual([]);
    setActive(0);
  }, []);

  const select = useCallback(
    (r: SearchResult) => {
      close();
      navigate(`/p/${r.module}/${r.feature}`);
      scrollToAnchor(r.anchor);
    },
    [close, navigate],
  );

  const reindex = useCallback(() => {
    setReindexing(true);
    api
      .reindex()
      .then((s) => {
        setStatus(s);
        setNeedsIndex(false);
        toast.success(
          `Search index rebuilt — ${s.fragment_count} fragments` +
            (s.has_embeddings ? " (semantic)" : " (lexical-only)"),
        );
        // Re-run the current query against the fresh index.
        setNonce((n) => n + 1);
      })
      .catch(() => toast.error("Failed to rebuild search index"))
      .finally(() => setReindexing(false));
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = results[active];
      if (r) select(r);
    }
  };

  // Keep the active row in view.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  // activeIdx is the keyboard index for main results, or null for visual rows
  // (mouse-only — they live in a separate space from the CLIP ranking).
  const renderRow = (r: SearchResult, key: string, activeIdx: number | null) => (
    <button
      key={key}
      data-idx={activeIdx ?? undefined}
      onMouseMove={activeIdx != null ? () => setActive(activeIdx) : undefined}
      onClick={() => select(r)}
      className={cn(
        "w-full text-left px-4 py-2.5 flex gap-3 border-b hairline last:border-b-0 transition-colors",
        activeIdx != null && activeIdx === active ? "bg-accent" : "hover:bg-accent/40",
      )}
    >
      {r.kind === "image" && r.image && (
        <img
          src={assetUrl(r.module, r.feature, r.image)}
          alt=""
          loading="lazy"
          className="h-12 w-12 shrink-0 rounded border hairline object-cover bg-muted"
        />
      )}
      <div className="flex flex-col gap-0.5 min-w-0 flex-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="shrink-0 font-mono text-[9px] uppercase tracking-wider text-muted-foreground border hairline rounded px-1 py-px">
            {KIND_LABEL[r.kind] ?? r.kind}
          </span>
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{r.label}</span>
          <span className="ml-auto shrink-0 flex items-center gap-1 text-[11px] text-muted-foreground/70 truncate">
            <FileText className="h-3 w-3 shrink-0" />
            {r.feature_name}
          </span>
        </div>
        <div className="text-[13px] leading-snug text-foreground/80 line-clamp-2">
          {highlight(r.snippet, query)}
        </div>
      </div>
    </button>
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-background/60 backdrop-blur-sm pt-[12vh] px-4"
      onMouseDown={close}
    >
      <div
        className="w-full max-w-2xl rounded-lg border hairline bg-popover text-popover-foreground shadow-2xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Input row */}
        <div className="flex items-center gap-3 px-4 border-b hairline">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search rules, requirements, bugs…"
            className="flex-1 bg-transparent py-3.5 text-[15px] outline-none placeholder:text-muted-foreground"
          />
          {loading && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />}
          <kbd className="hidden sm:block font-mono text-[10px] text-muted-foreground border hairline rounded px-1.5 py-0.5">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[52vh] overflow-y-auto">
          {needsIndex ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">
              <p>No search index yet.</p>
              {!IS_READONLY && (
                <button
                  onClick={reindex}
                  disabled={reindexing}
                  className="mt-3 inline-flex items-center gap-2 rounded-md border hairline px-3 py-1.5 text-foreground hover:bg-accent transition-colors disabled:opacity-50"
                >
                  {reindexing ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" />
                  )}
                  Build index
                </button>
              )}
            </div>
          ) : query.trim() && !loading && results.length === 0 && visual.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">
              No matches for “{query.trim()}”.
            </div>
          ) : (
            <>
              {results.map((r, i) => renderRow(r, `${r.ref}#${r.anchor}-${i}`, i))}
              {visual.length > 0 && (
                <>
                  <div className="px-4 pt-3 pb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                    <ImageIcon className="h-3 w-3" />
                    Visually similar
                  </div>
                  {visual.map((r, i) => renderRow(r, `v-${r.ref}#${r.anchor}-${i}`, null))}
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-4 py-2 border-t hairline text-[11px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <CornerDownLeft className="h-3 w-3" /> open
            </span>
            <span>↑↓ navigate</span>
            {status?.exists && (
              <span className="hidden sm:inline">
                {status.fragment_count} indexed · {timeAgo(status.indexed_at)}
                {status.has_embeddings ? " · semantic" : " · lexical"}
              </span>
            )}
          </div>
          {!IS_READONLY && (
            <button
              onClick={reindex}
              disabled={reindexing}
              className="inline-flex items-center gap-1.5 hover:text-foreground transition-colors disabled:opacity-50"
              title="Rebuild the search index from the current PRDs"
            >
              {reindexing ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Reindex
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
