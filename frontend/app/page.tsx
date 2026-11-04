import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 items-center px-6 py-16">
      <section className="max-w-3xl space-y-8">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-700">
          Your documents, understood
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-slate-950 sm:text-6xl">
          AI Knowledge Assistant
        </h1>
        <p className="max-w-2xl text-lg leading-8 text-slate-600">
          Bring your PDFs, ask questions in plain language, and explore answers
          grounded in cited sources.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            className="rounded-lg bg-slate-950 px-5 py-3 font-semibold text-white hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
            href="/signup"
          >
            Create an account
          </Link>
          <Link
            className="rounded-lg border border-slate-300 px-5 py-3 font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-700"
            href="/login"
          >
            Log in
          </Link>
        </div>
      </section>
    </main>
  );
}
