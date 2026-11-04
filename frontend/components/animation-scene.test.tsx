import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnimationScene } from "./animation-scene";

let intersectionCallback: IntersectionObserverCallback | undefined;

class MockIntersectionObserver {
  constructor(callback: IntersectionObserverCallback) {
    intersectionCallback = callback;
  }

  observe() {}
  disconnect() {}
  unobserve() {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

function intersectionEntry(
  target: Element,
  isIntersecting: boolean,
): IntersectionObserverEntry {
  const bounds = new DOMRectReadOnly();
  return {
    boundingClientRect: bounds,
    intersectionRatio: isIntersecting ? 1 : 0,
    intersectionRect: bounds,
    isIntersecting,
    rootBounds: null,
    target,
    time: 0,
  };
}

describe("AnimationScene", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    intersectionCallback = undefined;
  });

  it("starts only in view and pauses when the tab is hidden or the scene leaves view", () => {
    vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });

    const { container } = render(<AnimationScene scene="hero" />);
    const scene = container.firstElementChild as HTMLElement;
    expect(scene.getAttribute("data-active")).toBe("false");

    act(() => {
      intersectionCallback?.(
        [intersectionEntry(scene, true)],
        {} as IntersectionObserver,
      );
    });
    expect(scene.getAttribute("data-active")).toBe("true");

    act(() => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: "hidden",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(scene.getAttribute("data-active")).toBe("false");

    act(() => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: "visible",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(scene.getAttribute("data-active")).toBe("true");

    act(() => {
      intersectionCallback?.(
        [intersectionEntry(scene, false)],
        {} as IntersectionObserver,
      );
    });
    expect(scene.getAttribute("data-active")).toBe("false");
    expect(scene.querySelector("svg")?.getAttribute("aria-hidden")).toBeNull();
    expect(scene.getAttribute("aria-hidden")).toBe("true");
  });
});
