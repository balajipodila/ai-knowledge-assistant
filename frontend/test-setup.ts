import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn((path: string) => window.history.replaceState({}, "", path)),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => window.location.pathname,
  useRouter: () => routerMocks,
}));

if (typeof HTMLDialogElement !== "undefined") {
  // jsdom has dialog elements but does not implement the modal open/close methods.
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
  };
}

if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.history.replaceState({}, "", "/");
  vi.restoreAllMocks();
});
