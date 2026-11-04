import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Create an account to upload PDFs and ask questions with citations.",
};

export default function SignupPage() {
  return <AuthForm mode="signup" />;
}
