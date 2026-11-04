import type { Metadata } from "next";

import { DashboardOverview } from "@/components/dashboard-overview";
import { ProtectedRoute } from "@/components/protected-route";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Review your uploaded documents and their processing status.",
};

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardOverview />
    </ProtectedRoute>
  );
}
