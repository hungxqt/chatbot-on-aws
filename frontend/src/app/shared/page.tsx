import { Suspense } from "react";
import { SharedConversationClient } from "./client";

export default function SharedConversationPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-muted-foreground animate-pulse">Loading...</div>
        </div>
      }
    >
      <SharedConversationClient />
    </Suspense>
  );
}
