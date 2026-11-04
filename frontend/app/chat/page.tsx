import { ProtectedRoute } from "@/components/protected-route";

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-800">
          Ask your documents
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
          Cited chat
        </h1>
        <p className="mt-3 text-slate-600">
          Asking questions and viewing citations arrive in milestone F3.
        </p>
      </main>
    </ProtectedRoute>
  );
}
