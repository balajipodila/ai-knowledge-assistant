import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("home page", () => {
  it("explains the product, Gemini data use, and its grounded-answer design", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Find the useful pages in what you already know.",
    );
    expect(
      screen.getByText(/text extracted from uploaded PDFs is sent to the Google Gemini API/i),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeTruthy();
    for (const step of [
      "Upload a PDF",
      "Extract and split the text",
      "Create embeddings",
      "Search with pgvector",
      "Draft an answer",
      "Show the sources",
    ]) {
      expect(screen.getByRole("heading", { name: step })).toBeTruthy();
    }
    expect(screen.getByText(/without calling the chat generation model/i)).toBeTruthy();
    expect(screen.getByText(/Illustrative example — not real output/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Create an account" }).getAttribute("href"))
      .toBe("/signup");
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href"))
      .toBe("/login");
    const githubLink = screen.getByRole("link", { name: "View the project on GitHub" });
    expect(githubLink.getAttribute("href")).toBe(
      "https://github.com/balajipodila/ai-knowledge-assistant",
    );
    expect(githubLink.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
