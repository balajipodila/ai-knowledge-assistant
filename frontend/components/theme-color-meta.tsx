"use client";

import { useEffect } from "react";

export function ThemeColorMeta() {
  useEffect(() => {
    const color = getComputedStyle(document.documentElement)
      .getPropertyValue("--obsidian-950")
      .trim();
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (color && meta) meta.content = color;
  }, []);

  return null;
}
