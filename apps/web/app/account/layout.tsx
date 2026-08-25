import type { Metadata } from "next";
import AccountGate from "@/components/auth/AccountGate";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AccountLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AccountGate>{children}</AccountGate>;
}
