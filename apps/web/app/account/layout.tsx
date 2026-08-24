import AccountGate from "@/components/auth/AccountGate";

export default function AccountLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <AccountGate>{children}</AccountGate>;
}
