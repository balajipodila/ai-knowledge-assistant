import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
  description: "The page you requested could not be found.",
};

export default function NotFound() {
  return (
    <main
      aria-labelledby="not-found-title"
      className="workspace-page not-found-page"
      id="main-content"
    >
      <section className="glass-panel not-found-card">
        <p className="eyebrow">404 · Not found</p>
        <h1 className="page-title" id="not-found-title">
          This page is not here.
        </h1>
        <p className="page-description">
          The link may be out of date, or the address may have been entered incorrectly.
        </p>
        <Link className="button-primary" href="/">
          Back to home
        </Link>
      </section>
    </main>
  );
}
