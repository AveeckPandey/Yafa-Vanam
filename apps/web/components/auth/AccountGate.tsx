"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export default function AccountGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace(`/auth/sign-in?return_to=${encodeURIComponent(pathname)}`);
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) return <main className="auth-session-loading" aria-live="polite"><span aria-hidden="true" /><p>Checking your secure session…</p></main>;
  if (!isAuthenticated) return null;
  return <>{children}</>;
}
