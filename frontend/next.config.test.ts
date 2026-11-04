import { describe, expect, it } from "vitest";

import nextConfig from "./next.config";

describe("Next.js security headers", () => {
  it("sets the browser security headers and a same-origin API policy", async () => {
    const headerRules = await nextConfig.headers?.();
    if (!headerRules) {
      throw new Error("Next.js security headers are not configured.");
    }

    const rule = headerRules.find(({ source }) => source === "/:path*");
    if (!rule) {
      throw new Error("The security header route matcher is not configured.");
    }
    const headers = new Map(rule.headers.map(({ key, value }) => [key, value]));

    expect(headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(headers.get("Referrer-Policy")).toBe("no-referrer");
    expect(headers.get("X-Frame-Options")).toBe("DENY");
    expect(headers.get("Content-Security-Policy")).toContain(
      "frame-ancestors 'none'",
    );
    expect(headers.get("Content-Security-Policy")).toContain(
      "connect-src 'self'",
    );
  });
});
