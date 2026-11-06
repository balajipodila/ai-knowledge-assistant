"use client";

import { useEffect, useState } from "react";

const COLD_START_DELAY_MS = 2_000;

type ColdStartStatusProps = {
  children: string;
  className?: string;
};

export function ColdStartStatus({ children, className }: ColdStartStatusProps) {
  const [mayBeColdStarting, setMayBeColdStarting] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(
      () => setMayBeColdStarting(true),
      COLD_START_DELAY_MS,
    );
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <p aria-live="polite" className={className} role="status">
      {children}
      {mayBeColdStarting && (
        <>
          <br />
          The service may be waking up. This first request can take a little
          longer; please keep this page open.
        </>
      )}
    </p>
  );
}
