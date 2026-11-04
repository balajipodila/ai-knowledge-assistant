import type { Metadata } from "next";

import { ProtectedRoute } from "@/components/protected-route";
import { DocumentsManager } from "@/components/documents-manager";

export const metadata: Metadata = {
  title: "Documents",
  description: "Upload and manage your PDF documents.",
};

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsManager />
    </ProtectedRoute>
  );
}
