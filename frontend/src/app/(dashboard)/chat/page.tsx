"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { ChatContainer, ConversationSidebar } from "@/components/chat";
import { useConversationStore } from "@/stores";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const { setCurrentConversationId } = useConversationStore();

  useEffect(() => {
    const conversationId = searchParams.get("id");
    if (conversationId) {
      setCurrentConversationId(conversationId);
    }
  }, [searchParams, setCurrentConversationId]);

  return (
    <div className="-m-3 flex min-h-0 flex-1 sm:-m-6">
      <ConversationSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">
          <ChatContainer />
        </div>
      </div>
    </div>
  );
}
