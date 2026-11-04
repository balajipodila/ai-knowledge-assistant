import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to access your PDFs and cited chat.",
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
