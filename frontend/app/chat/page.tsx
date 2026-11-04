import type { Metadata } from "next";

import { ProtectedRoute } from "@/components/protected-route";
import { ChatInterface } from "@/components/chat-interface";

export const metadata: Metadata = {
  title: "Cited chat",
  description: "Ask questions about your PDFs and review cited source passages.",
};

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <ChatInterface />
    </ProtectedRoute>
  );
}
