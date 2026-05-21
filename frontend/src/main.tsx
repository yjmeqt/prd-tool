import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { App } from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

async function waitForPywebview(): Promise<void> {
  if (typeof window === "undefined") return;
  if (window.pywebview) return;
  // Under file:// we're almost certainly inside pywebview — wait generously so
  // useState initializers, useEffect bodies, and useQuery first-fetch all see
  // the bridge. Outside file:// (browser, dev server) bail out fast.
  const isFileProtocol = window.location.protocol === "file:";
  const timeoutMs = isFileProtocol ? 5000 : 50;
  await new Promise<void>((resolve) => {
    const t = setTimeout(resolve, timeoutMs);
    window.addEventListener(
      "pywebviewready",
      () => {
        clearTimeout(t);
        resolve();
      },
      { once: true },
    );
  });
}

void (async () => {
  await waitForPywebview();
  if (window.pywebview) {
    try {
      window.__prdAssetRoot = await window.pywebview.api.asset_root();
    } catch {
      // ignore — assets will 404 but the UI loads.
    }
  }
  const Router = window.pywebview ? HashRouter : BrowserRouter;
  const routerProps = window.pywebview ? {} : { basename: import.meta.env.BASE_URL };

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <Router {...routerProps}>
          <App />
        </Router>
      </QueryClientProvider>
    </React.StrictMode>,
  );
})();
