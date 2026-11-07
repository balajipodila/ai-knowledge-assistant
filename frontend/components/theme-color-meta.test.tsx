import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ThemeColorMeta } from "./theme-color-meta";

describe("ThemeColorMeta", () => {
  afterEach(() => {
    document.documentElement.style.removeProperty("--forest-950");
  });

  it("uses the shared forest token for browser theme color", async () => {
    document.documentElement.style.setProperty("--forest-950", "Canvas");
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = "transparent";
    document.head.append(meta);

    render(<ThemeColorMeta />);
    await waitFor(() => expect(meta.content).toBe("Canvas"));

    meta.remove();
  });
});
