export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
      <section className="max-w-2xl space-y-6 text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-300">
          Your documents, understood
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          AI Knowledge Assistant
        </h1>
        <p className="text-lg leading-8 text-slate-300">
          Upload your documents, ask questions in plain language, and get
          answers grounded in cited sources.
        </p>
        <p className="text-sm text-slate-400">
          The application foundation is ready. Document features are coming in
          later milestones.
        </p>
      </section>
    </main>
  );
}
