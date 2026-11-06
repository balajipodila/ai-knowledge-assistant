import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ColdStartStatus } from "./cold-start-status";

describe("ColdStartStatus", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("explains a possible cold start when loading takes longer", () => {
    render(<ColdStartStatus>Loading your dashboard…</ColdStartStatus>);

    expect(screen.getByRole("status").textContent).toContain("Loading your dashboard…");
    expect(screen.getByRole("status").textContent).not.toContain("waking up");

    act(() => vi.advanceTimersByTime(2_000));

    expect(screen.getByRole("status").textContent).toContain(
      "The service may be waking up",
    );
    expect(screen.getByRole("status").textContent).toContain("keep this page open");
  });
});
