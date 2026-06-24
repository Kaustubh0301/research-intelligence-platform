import type { Metadata } from "next";
import { ChatPageClient } from "@/components/chat/ChatPageClient";

export const metadata: Metadata = {
  title: "Research Assistant — Research Intelligence Platform",
};

export default function ChatPage() {
  return <ChatPageClient />;
}
