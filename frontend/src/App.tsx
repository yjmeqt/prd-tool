import { Route, Routes } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { HomePage } from "@/pages/Home";
import { FeaturePage } from "@/pages/Feature";
import { useSseInvalidation } from "@/useSse";
import { useSystemTheme } from "@/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AlertCircle } from "lucide-react";
import { IS_READONLY } from "@/lib/staticMode";

export function App() {
  useSystemTheme();
  const sse = useSseInvalidation();
  return (
    <TooltipProvider>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar />
        <main className="flex-1 min-w-0 relative">
          {/* Masthead */}
          <div className="sticky top-0 z-20 border-b hairline bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
            <div className="mx-auto max-w-5xl px-10 h-12 flex items-center justify-between">
              <div className="flex items-center gap-3 eyebrow text-muted-foreground">
                <span>Vol. 01</span>
                <span className="text-rule">·</span>
                <span>Product Requirements</span>
                {IS_READONLY && (
                  <>
                    <span className="text-rule">·</span>
                    <span className="border hairline px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider">
                      Read-only
                    </span>
                  </>
                )}
              </div>
              <div className="eyebrow text-muted-foreground tabular-nums">
                {new Date().toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "2-digit",
                })}
              </div>
            </div>
          </div>

          <div className="mx-auto max-w-5xl px-10 py-10">
            {sse === "error" && (
              <div className="mb-8 flex items-start gap-3 border-l-2 border-destructive bg-destructive/5 px-4 py-3 text-sm">
                <AlertCircle className="h-4 w-4 mt-0.5 text-destructive shrink-0" />
                <div>
                  <div className="font-medium text-destructive">Live updates disconnected</div>
                  <div className="text-muted-foreground mt-0.5">
                    The dashboard server may have stopped. Pages won't refresh from disk until the
                    connection recovers.
                  </div>
                </div>
              </div>
            )}
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/p/:module/:feature" element={<FeaturePage />} />
            </Routes>
          </div>
        </main>
        <Toaster position="bottom-right" richColors />
      </div>
    </TooltipProvider>
  );
}
