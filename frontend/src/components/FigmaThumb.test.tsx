import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FigmaThumb } from "./FigmaThumb";

describe("FigmaThumb", () => {
  it("renders the name as link text and points at figma.com/design/", () => {
    render(<FigmaThumb name="Sign-in screen" fileKey="ABC123" node="42-7" />);
    const link = screen.getByRole("link", { name: /sign-in screen/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("figma.com/design/ABC123/"));
    expect(link).toHaveAttribute("href", expect.stringContaining("node-id=42-7"));
  });

  it("falls back to the node id when no name is given", () => {
    render(<FigmaThumb name="" fileKey="X" node="9-3" />);
    expect(screen.getByText("9-3")).toBeInTheDocument();
  });

  it("converts a colon-separated node id to dash-form for the URL", () => {
    render(<FigmaThumb name="ns" fileKey="X" node="42:7" />);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      expect.stringContaining("node-id=42-7"),
    );
  });

  it("opens in a new tab safely", () => {
    render(<FigmaThumb name="a" fileKey="X" node="1-2" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });
});
