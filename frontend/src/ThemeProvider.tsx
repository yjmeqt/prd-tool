import { useEffect } from "react";

/**
 * Passive theme mirror: applies the `dark` class on <html> whenever the
 * operating system reports a dark color scheme, and removes it otherwise.
 * Listens for system-level changes so the dashboard flips live, without a
 * reload, when the user toggles their OS theme.
 *
 * No user control, no persistence — the OS is the only source of truth.
 */
export function useSystemTheme(): void {
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = (dark: boolean) => {
      const root = document.documentElement;
      root.classList.toggle("dark", dark);
      root.style.colorScheme = dark ? "dark" : "light";
    };
    apply(mq.matches);
    const handler = (e: MediaQueryListEvent) => apply(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
}
