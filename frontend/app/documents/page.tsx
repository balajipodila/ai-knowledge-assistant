import { ProtectedRoute } from "@/components/protected-route";
import { DocumentsManager } from "@/components/documents-manager";

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsManager />
    </ProtectedRoute>
  );
}
