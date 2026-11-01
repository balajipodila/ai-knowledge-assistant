import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("home page", () => {
  it("introduces the AI Knowledge Assistant", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "AI Knowledge Assistant" }),
    ).toBeTruthy();
  });
});
