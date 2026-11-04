import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, SESSION_EXPIRED_EVENT } from "./api";
import { saveSession } from "./session";

function response(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
    headers: new Headers(headers),
  } as Response;
}

describe("typed API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the session bearer token without logging it", async () => {
    saveSession({
      access_token: "unit-test-token",
      expires_in: 60,
      user: { id: "user-1", email: "person@example.test", created_at: "" },
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(response(200, { ok: true }));

    await expect(apiRequest<{ ok: boolean }>("/auth/me")).resolves.toEqual({
      ok: true,
    });

    expect(fetchMock.mock.calls[0][1]?.headers).toBeInstanceOf(Headers);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization"))
      .toBe("Bearer unit-test-token");
  });

  it("clears expired authentication and emits the expiry event on 401", async () => {
    saveSession({
      access_token: "unit-test-token",
      expires_in: 60,
      user: { id: "user-1", email: "person@example.test", created_at: "" },
    });
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response(401, {
        error: { code: "UNAUTHORIZED", message: "private details" },
      }),
    );

    await expect(apiRequest("/auth/me")).rejects.toMatchObject({
      status: 401,
      message: "Email or password is incorrect.",
    });

    expect(window.sessionStorage.length).toBe(0);
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it("maps 422 field details and overload responses to friendly errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(422, {
        detail: [{ loc: ["body", "email"], msg: "invalid email" }],
      }),
    );

    await expect(
      apiRequest("/auth/signup", { auth: false, body: {} }),
    ).rejects.toMatchObject({
      status: 422,
      fields: { email: "invalid email" },
      message: "Check the highlighted fields and try again.",
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(
        429,
        { error: { code: "TOO_MANY_REQUESTS" } },
        { "Retry-After": "17" },
      ),
    );
    await expect(apiRequest("/chat")).rejects.toMatchObject({
      status: 429,
      message: "The service is busy. Please try again in 17 seconds.",
      retryAfterSeconds: 17,
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      response(503, { error: { code: "CHAT_UNAVAILABLE", message: "internal" } }),
    );
    await expect(apiRequest("/chat")).rejects.toMatchObject({
      status: 503,
      message: "The service is temporarily unavailable. Please try again shortly.",
    });
  });

  it("uses a friendly network error instead of exposing exception details", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new Error("private network internals"),
    );

    await expect(apiRequest("/auth/me")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      message: "Could not connect to the service. Check your connection and try again.",
    });
  });
});
