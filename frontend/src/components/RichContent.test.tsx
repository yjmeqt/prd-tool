import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RichContent } from "./RichContent";
import { parsePrdHref, rewriteImgSrc } from "@/lib/richContent";

describe("rewriteImgSrc", () => {
  it("rewrites a relative src to /api/prd-asset/<module>/<feature>/<path>", () => {
    const out = rewriteImgSrc('<img src="screenshots/err.png" alt="x"/>', "content", "rich");
    expect(out).toContain('src="/api/prd-asset/content/rich/screenshots/err.png"');
  });

  it("leaves absolute http/https/data URLs untouched", () => {
    expect(rewriteImgSrc('<img src="https://x/y.png"/>', "m", "f")).toBe(
      '<img src="https://x/y.png"/>',
    );
    expect(rewriteImgSrc('<img src="data:image/png;base64,xx"/>', "m", "f")).toBe(
      '<img src="data:image/png;base64,xx"/>',
    );
    expect(rewriteImgSrc('<img src="/already/served"/>', "m", "f")).toBe(
      '<img src="/already/served"/>',
    );
  });

  it("encodes path segments", () => {
    const out = rewriteImgSrc('<img src="a folder/b.png"/>', "m", "f");
    expect(out).toContain("/api/prd-asset/m/f/a%20folder/b.png");
  });

  it("rewrites to file:// when native asset root is set", () => {
    const w = window as unknown as Record<string, unknown>;
    w.__prdAssetRoot = "/abs/prd";
    try {
      const out = rewriteImgSrc('<img src="screenshots/err.png"/>', "content", "rich");
      expect(out).toContain('src="file:///abs/prd/content/screenshots/err.png"');
    } finally {
      delete w.__prdAssetRoot;
    }
  });

  it("leaves file:// URLs untouched", () => {
    expect(rewriteImgSrc('<img src="file:///x/y.png"/>', "m", "f")).toBe(
      '<img src="file:///x/y.png"/>',
    );
  });
});

describe("parsePrdHref", () => {
  it("parses module/feature with no fragment", () => {
    expect(parsePrdHref("prd:auth/login")).toEqual({
      module: "auth",
      feature: "login",
      fragment: null,
    });
  });

  it("parses with a requirement fragment", () => {
    expect(parsePrdHref("prd:dashboard/viewer#R3")).toEqual({
      module: "dashboard",
      feature: "viewer",
      fragment: "R3",
    });
  });

  it("parses with a rule fragment", () => {
    expect(parsePrdHref("prd:dashboard/viewer#R3.foo_bar")).toEqual({
      module: "dashboard",
      feature: "viewer",
      fragment: "R3.foo_bar",
    });
  });

  it("returns null for non-prd hrefs", () => {
    expect(parsePrdHref("https://x")).toBeNull();
    expect(parsePrdHref("prd:onlyone")).toBeNull();
  });
});

describe("RichContent", () => {
  it("renders HTML markup", () => {
    render(
      <MemoryRouter>
        <RichContent html="Use <code>x</code>" module="m" feature="f" />
      </MemoryRouter>,
    );
    expect(screen.getByText("x").tagName.toLowerCase()).toBe("code");
  });

  it("rewrites relative img src", () => {
    const { container } = render(
      <MemoryRouter>
        <RichContent html='<img src="a.png" alt="a"/>' module="m" feature="f" />
      </MemoryRouter>,
    );
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toBe("/api/prd-asset/m/f/a.png");
  });

  it("renders nothing when html is empty", () => {
    const { container } = render(
      <MemoryRouter>
        <RichContent html="" module="m" feature="f" />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });
});
