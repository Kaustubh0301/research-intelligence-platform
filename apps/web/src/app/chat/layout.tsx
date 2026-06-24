import { SessionProvider } from "@/components/sessions/SessionContext";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
