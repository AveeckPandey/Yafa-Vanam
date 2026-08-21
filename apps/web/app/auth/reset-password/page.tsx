import { Suspense } from "react";
import AuthForm from "../AuthForm";

export default function ResetPasswordPage() {
  return <Suspense><AuthForm mode="reset-password" /></Suspense>;
}
