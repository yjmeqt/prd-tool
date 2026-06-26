import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Minus,
  Plus,
  RotateCw,
  X,
} from "lucide-react";

/**
 * Fullscreen image lightbox for PRD rich-content images.
 *
 * Mounted once near the app root. It delegates clicks on any `.prd-prose img`
 * in the document, builds a gallery from every such image (in document order),
 * and opens a fullscreen overlay with zoom / pan / rotate, keyboard shortcuts,
 * and prev/next navigation across all images on the page.
 *
 * Delegation (rather than per-image wiring) keeps RichContent untouched and
 * works for any number of RichContent instances on a page, across server,
 * native (file://), and static-export modes — the <img src> is already
 * resolved by the time we read it here.
 */

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 8;
const ZOOM_STEP = 1.2;

type GalleryImage = { src: string; alt: string };

function collectGallery(): GalleryImage[] {
  const imgs = Array.from(document.querySelectorAll<HTMLImageElement>(".prd-prose img"));
  return imgs.map((img) => ({ src: img.currentSrc || img.src, alt: img.alt || "" }));
}

/** Produce a PNG blob from the displayed image.
 *
 *  Preferred path draws the already-decoded <img> onto a canvas — no extra
 *  network request, and it works for `file://` sources in native mode where a
 *  fetch would be blocked. Falls back to fetching the src directly if the
 *  canvas is tainted or unavailable. */
async function imageToPngBlob(el: HTMLImageElement, src: string): Promise<Blob | null> {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = el.naturalWidth;
    canvas.height = el.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (ctx && canvas.width && canvas.height) {
      ctx.drawImage(el, 0, 0);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (blob) return blob;
    }
  } catch {
    // Canvas tainted or unsupported — fall through to a direct fetch.
  }
  try {
    return await (await fetch(src)).blob();
  } catch {
    return null;
  }
}

export function Lightbox() {
  const [gallery, setGallery] = useState<GalleryImage[]>([]);
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);

  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const [copied, setCopied] = useState<"idle" | "ok" | "err">("idle");
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);

  const current = gallery[index];

  const copyImage = useCallback(async () => {
    const el = imgRef.current;
    if (!el || !current) return;
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
        throw new Error("clipboard image write unsupported");
      }
      const blob = await imageToPngBlob(el, current.src);
      if (!blob) throw new Error("could not encode image");
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      setCopied("ok");
    } catch {
      setCopied("err");
    }
    window.setTimeout(() => setCopied("idle"), 1600);
  }, [current]);

  const saveImage = useCallback(async () => {
    const el = imgRef.current;
    if (!el || !current) return;
    const blob = await imageToPngBlob(el, current.src);
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filenameFor(current);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [current]);

  const resetView = useCallback(() => {
    setZoom(1);
    setRotation(0);
    setOffset({ x: 0, y: 0 });
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setMenu(null);
    drag.current = null;
    setDragging(false);
  }, []);

  const goTo = useCallback(
    (next: number, total: number) => {
      const wrapped = ((next % total) + total) % total;
      setIndex(wrapped);
      setMenu(null);
      resetView();
    },
    [resetView],
  );

  const zoomBy = useCallback((factor: number) => {
    setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * factor)));
  }, []);

  // Delegate clicks on rich-content images anywhere in the document.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey) return;
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const img = target.closest<HTMLImageElement>(".prd-prose img");
      if (!img) return;
      // Don't hijack images wrapped in a link.
      if (img.closest("a")) return;
      e.preventDefault();
      const items = collectGallery();
      const src = img.currentSrc || img.src;
      const at = items.findIndex((it) => it.src === src);
      setGallery(items);
      setIndex(at >= 0 ? at : 0);
      resetView();
      setOpen(true);
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [resetView]);

  // Keyboard shortcuts while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case "Escape":
          if (menu) setMenu(null);
          else close();
          break;
        case "ArrowRight":
          if (gallery.length > 1) goTo(index + 1, gallery.length);
          break;
        case "ArrowLeft":
          if (gallery.length > 1) goTo(index - 1, gallery.length);
          break;
        case "+":
        case "=":
          zoomBy(ZOOM_STEP);
          break;
        case "-":
        case "_":
          zoomBy(1 / ZOOM_STEP);
          break;
        case "0":
          resetView();
          break;
        case "r":
        case "R":
          setRotation((r) => (r + 90) % 360);
          break;
        case "c":
        case "C":
          void copyImage();
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, gallery.length, menu, close, goTo, zoomBy, resetView, copyImage]);

  // Lock body scroll while open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const onWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
    },
    [zoomBy],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (zoom <= 1) return;
      (e.target as Element).setPointerCapture(e.pointerId);
      drag.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
      setDragging(true);
    },
    [zoom, offset],
  );

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!drag.current) return;
    setOffset({
      x: drag.current.ox + (e.clientX - drag.current.x),
      y: drag.current.oy + (e.clientY - drag.current.y),
    });
  }, []);

  const onPointerUp = useCallback(() => {
    drag.current = null;
    setDragging(false);
  }, []);

  if (!open || !current) return null;

  const hasMany = gallery.length > 1;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/90 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Image viewer"
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 px-4 py-2.5 text-white/90">
        <div className="min-w-0 truncate text-sm">
          {current.alt && <span className="opacity-80">{current.alt}</span>}
          {hasMany && (
            <span className="ml-2 tabular-nums text-xs opacity-60">
              {index + 1} / {gallery.length}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <ToolBtn label="Zoom out (-)" onClick={() => zoomBy(1 / ZOOM_STEP)}>
            <Minus className="h-4 w-4" />
          </ToolBtn>
          <button
            onClick={resetView}
            className="rounded px-2 py-1 text-xs tabular-nums hover:bg-white/15"
            title="Reset (0)"
          >
            {Math.round(zoom * 100)}%
          </button>
          <ToolBtn label="Zoom in (+)" onClick={() => zoomBy(ZOOM_STEP)}>
            <Plus className="h-4 w-4" />
          </ToolBtn>
          <ToolBtn label="Rotate (R)" onClick={() => setRotation((r) => (r + 90) % 360)}>
            <RotateCw className="h-4 w-4" />
          </ToolBtn>
          <ToolBtn
            label={copied === "ok" ? "Copied" : copied === "err" ? "Copy failed" : "Copy image (C)"}
            onClick={() => void copyImage()}
          >
            {copied === "ok" ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <Copy className={"h-4 w-4 " + (copied === "err" ? "text-red-400" : "")} />
            )}
          </ToolBtn>
          <ToolBtn label="Close (Esc)" onClick={close}>
            <X className="h-4 w-4" />
          </ToolBtn>
        </div>
      </div>

      {/* Stage */}
      <div
        className="relative flex-1 overflow-hidden"
        onWheel={onWheel}
        onClick={(e) => {
          if (e.target === e.currentTarget) close();
        }}
      >
        {hasMany && (
          <ToolBtn
            label="Previous (←)"
            onClick={() => goTo(index - 1, gallery.length)}
            className="absolute left-3 top-1/2 -translate-y-1/2 z-10 !p-2"
          >
            <ChevronLeft className="h-6 w-6" />
          </ToolBtn>
        )}
        {hasMany && (
          <ToolBtn
            label="Next (→)"
            onClick={() => goTo(index + 1, gallery.length)}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-10 !p-2"
          >
            <ChevronRight className="h-6 w-6" />
          </ToolBtn>
        )}
        <div className="flex h-full w-full items-center justify-center">
          <img
            ref={imgRef}
            src={current.src}
            alt={current.alt}
            draggable={false}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onContextMenu={(e) => {
              e.preventDefault();
              setMenu({ x: e.clientX, y: e.clientY });
            }}
            onDoubleClick={() => (zoom > 1 ? resetView() : zoomBy(ZOOM_STEP * ZOOM_STEP))}
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom}) rotate(${rotation}deg)`,
              cursor: zoom > 1 ? (dragging ? "grabbing" : "grab") : "zoom-in",
              transition: dragging ? "none" : "transform 120ms ease-out",
            }}
            className="max-h-full max-w-full select-none object-contain"
          />
        </div>
      </div>

      {/* Right-click context menu */}
      {menu && (
        <div
          className="fixed inset-0 z-20"
          onClick={() => setMenu(null)}
          onContextMenu={(e) => e.preventDefault()}
        >
          <div
            className="absolute min-w-[160px] overflow-hidden rounded-md border border-white/10 bg-neutral-900/95 py-1 text-sm text-white/90 shadow-xl backdrop-blur"
            style={{
              left: Math.min(menu.x, window.innerWidth - 180),
              top: Math.min(menu.y, window.innerHeight - 96),
            }}
          >
            <MenuItem
              onClick={() => {
                setMenu(null);
                void copyImage();
              }}
            >
              <Copy className="h-3.5 w-3.5" /> Copy image
            </MenuItem>
            <MenuItem
              onClick={() => {
                setMenu(null);
                void saveImage();
              }}
            >
              <Download className="h-3.5 w-3.5" /> Save image…
            </MenuItem>
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}

function MenuItem({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-white/15"
    >
      {children}
    </button>
  );
}

/** Best-effort download filename: basename of the src, ensured to end in an
 *  image extension, falling back to the alt text or a generic name. */
function filenameFor(img: GalleryImage): string {
  try {
    const path = decodeURIComponent(img.src.split(/[?#]/)[0]);
    const base = path.substring(path.lastIndexOf("/") + 1);
    if (base && /\.(png|jpe?g|gif|webp|svg)$/i.test(base)) return base;
    if (base) return `${base}.png`;
  } catch {
    // fall through
  }
  const fromAlt = img.alt
    .trim()
    .replace(/[^\w-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return `${fromAlt || "image"}.png`;
}

function ToolBtn({
  label,
  onClick,
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className={
        "rounded p-1.5 text-white/90 hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 " +
        (className ?? "")
      }
    >
      {children}
    </button>
  );
}
