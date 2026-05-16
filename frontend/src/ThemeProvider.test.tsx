import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSystemTheme } from "./ThemeProvider";

type Listener = (e: { matches: boolean }) => void;

function installMatchMedia(initial: boolean) {
  const listeners: Listener[] = [];
  const mq = {
    matches: initial,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_: string, l: Listener) => listeners.push(l),
    removeEventListener: (_: string, l: Listener) => {
      const i = listeners.indexOf(l);
      if (i >= 0) listeners.splice(i, 1);
    },
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
  window.matchMedia = vi.fn().mockReturnValue(mq);
  return {
    mq,
    fire(matches: boolean) {
      mq.matches = matches;
      listeners.forEach((l) => l({ matches }));
    },
  };
}

describe("useSystemTheme", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    document.documentElement.style.colorScheme = "";
  });
  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  it("adds the `dark` class when the OS reports dark on mount", () => {
    installMatchMedia(true);
    renderHook(() => useSystemTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("does not add the `dark` class when the OS reports light on mount", () => {
    installMatchMedia(false);
    renderHook(() => useSystemTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("flips live when the OS scheme changes", () => {
    const { fire } = installMatchMedia(false);
    renderHook(() => useSystemTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    fire(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fire(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
