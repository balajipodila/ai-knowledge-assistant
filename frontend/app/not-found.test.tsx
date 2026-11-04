import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NotFound from "./not-found";

describe("not found page", () => {
  it("explains the missing page and provides a home link", () => {
    render(<NotFound />);

    expect(
      screen.getByRole("heading", { name: "This page is not here." }),
    ).toBeTruthy();
    expect(screen.getByRole("main").id).toBe("main-content");
    expect(screen.getByRole("link", { name: "Back to home" }).getAttribute("href"))
      .toBe("/");
  });
});
