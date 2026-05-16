import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, ReactNode } from "react";
import { noteOwnWrite, useSseInvalidation } from "./useSse";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners = new Map<string, ((e: MessageEvent) => void)[]>();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, cb: (e: MessageEvent) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type)!.push(cb);
  }
  close() {
    this.closed = true;
  }
  fire(type: string) {
    this.listeners.get(type)?.forEach((cb) => cb(new MessageEvent(type)));
  }
}

function wrap(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
}

describe("useSseInvalidation", () => {
  beforeEach(() => {
    FakeEventSource.instances.length = 0;
    (globalThis as unknown as { EventSource: typeof FakeEventSource }).EventSource =
      FakeEventSource;
  });

  it("subscribes to /api/events and invalidates index + feature on prd_changed", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useSseInvalidation(), { wrapper: wrap(qc) });

    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/api/events");

    es.fire("prd_changed");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["index"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["feature"] });
  });

  it("suppresses invalidation if a recent own-write happened", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useSseInvalidation(), { wrapper: wrap(qc) });
    const es = FakeEventSource.instances[0];

    noteOwnWrite();
    es.fire("prd_changed");

    expect(spy).not.toHaveBeenCalled();
  });

  it("closes the EventSource on unmount", () => {
    const qc = new QueryClient();
    const { unmount } = renderHook(() => useSseInvalidation(), { wrapper: wrap(qc) });
    const es = FakeEventSource.instances[0];
    unmount();
    expect(es.closed).toBe(true);
  });
});
