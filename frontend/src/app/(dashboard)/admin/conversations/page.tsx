"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ChevronLeft, ChevronRight, MessageSquare, Search, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAdminConversations } from "@/hooks";
import type { AdminConversation, AdminUser } from "@/types";

const PAGE_SIZE = 50;

export default function AdminConversationsPage() {
  const router = useRouter();
  const {
    conversations,
    conversationsTotal,
    users,
    usersTotal,
    selectedConversation,
    isLoading,
    fetchConversations,
    fetchUsers,
    fetchConversationDetail,
    setSelectedConversation,
  } = useAdminConversations();

  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("conversations");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [convPage, setConvPage] = useState(0);
  const [usersPage, setUsersPage] = useState(0);

  useEffect(() => {
    fetchConversations({ limit: PAGE_SIZE });
    fetchUsers({ limit: PAGE_SIZE });
  }, [fetchConversations, fetchUsers]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === "conversations") {
        fetchConversations({
          search: search || undefined,
          user_id: selectedUserId || undefined,
          skip: convPage * PAGE_SIZE,
          limit: PAGE_SIZE,
        });
      } else {
        fetchUsers({ search: search || undefined, skip: usersPage * PAGE_SIZE, limit: PAGE_SIZE });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search, activeTab, selectedUserId, convPage, usersPage, fetchConversations, fetchUsers]);

  const handleViewConversation = async (conv: AdminConversation) => {
    await fetchConversationDetail(conv.id);
  };

  const handleUserClick = (user: AdminUser) => {
    setSelectedUserId(user.id);
    setActiveTab("conversations");
    setSearch("");
    setConvPage(0);
  };

  const convTotalPages = Math.ceil(conversationsTotal / PAGE_SIZE);
  const usersTotalPages = Math.ceil(usersTotal / PAGE_SIZE);

  // Read-only conversation preview
  if (selectedConversation) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 border-b p-4">
          <Button variant="ghost" size="icon" onClick={() => setSelectedConversation(null)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="font-semibold">{selectedConversation.title || "Untitled"}</h2>
            <p className="text-muted-foreground text-xs">
              {selectedConversation.messages.length} {"messages (read-only)"}
            </p>
          </div>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {selectedConversation.messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                <p className="mt-1 text-xs opacity-60">
                  {new Date(msg.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{"Admin: Conversations"}</h1>
        <p className="text-muted-foreground">{"Browse and manage all conversations and users."}</p>
      </div>

      <div className="mb-4 flex items-center gap-4">
        <div className="relative max-w-sm flex-1">
          <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
          <Input
            placeholder={"Search..."}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        {selectedUserId && (
          <Button variant="outline" size="sm" onClick={() => setSelectedUserId(null)}>
            {"Clear user filter"}
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
        <TabsList>
          <TabsTrigger value="conversations">
            <MessageSquare className="mr-2 h-4 w-4" />
            {"Conversations"} ({conversationsTotal})
          </TabsTrigger>
          <TabsTrigger value="users">
            <Users className="mr-2 h-4 w-4" />
            {"Users"} ({usersTotal})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="conversations" className="flex-1">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{"Title"}</TableHead>
                <TableHead>{"Owner"}</TableHead>
                <TableHead>{"Messages"}</TableHead>
                <TableHead>{"Created"}</TableHead>
                <TableHead>{"Status"}</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 6 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : conversations.map((conv) => (
                    <TableRow key={conv.id}>
                      <TableCell className="font-medium">{conv.title || "Untitled"}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {conv.user_email || "—"}
                      </TableCell>
                      <TableCell>{conv.message_count}</TableCell>
                      <TableCell>{new Date(conv.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        {conv.is_archived ? (
                          <Badge variant="secondary">Archived</Badge>
                        ) : (
                          <Badge variant="default">Active</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewConversation(conv)}
                        >
                          {"View"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
              {!isLoading && conversations.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground py-8 text-center">
                    {"No conversations found."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {convTotalPages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <span className="text-muted-foreground text-sm">
                Page {convPage + 1} of {convTotalPages} &middot; {conversationsTotal} total
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConvPage((p) => Math.max(0, p - 1))}
                  disabled={convPage === 0 || isLoading}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConvPage((p) => Math.min(convTotalPages - 1, p + 1))}
                  disabled={convPage >= convTotalPages - 1 || isLoading}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="users" className="flex-1">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{"Email"}</TableHead>
                <TableHead>{"Name"}</TableHead>
                <TableHead>{"Conversations"}</TableHead>
                <TableHead>{"Status"}</TableHead>
                <TableHead>{"Joined"}</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 6 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{user.email}</TableCell>
                      <TableCell>{user.full_name || "—"}</TableCell>
                      <TableCell>{user.conversation_count}</TableCell>
                      <TableCell>
                        {user.is_active ? (
                          <Badge variant="default">Active</Badge>
                        ) : (
                          <Badge variant="destructive">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell>{new Date(user.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => handleUserClick(user)}>
                          {"View chats"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
              {!isLoading && users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground py-8 text-center">
                    {"No users found."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {usersTotalPages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <span className="text-muted-foreground text-sm">
                Page {usersPage + 1} of {usersTotalPages} &middot; {usersTotal} total
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setUsersPage((p) => Math.max(0, p - 1))}
                  disabled={usersPage === 0 || isLoading}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setUsersPage((p) => Math.min(usersTotalPages - 1, p + 1))}
                  disabled={usersPage >= usersTotalPages - 1 || isLoading}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
