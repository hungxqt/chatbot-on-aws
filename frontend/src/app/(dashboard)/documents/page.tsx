"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { useAuth } from "@/hooks";
import {
  Button,
  Card,
  CardContent,
  Input,
  Badge,
  Skeleton,
  Spinner,
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui";
import {
  Upload,
  FileText,
  Trash2,
  Download,
  FolderOpen,
  Search,
  RefreshCw,
} from "lucide-react";
import {
  listSharedDocuments,
  uploadSharedDocument,
  deleteSharedDocument,
  getSharedDocumentDownloadUrl,
  type SharedDocument,
} from "@/lib/shared-documents-api";
import { Breadcrumb } from "@/components/layout/breadcrumb";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function fileIcon(contentType: string) {
  const color =
    contentType.includes("pdf")
      ? "text-red-500"
      : contentType.includes("image")
        ? "text-blue-500"
        : contentType.includes("word") || contentType.includes("document")
          ? "text-blue-600"
          : contentType.includes("sheet") || contentType.includes("csv")
            ? "text-green-600"
            : "text-muted-foreground";
  return <FileText className={`h-5 w-5 ${color}`} />;
}

export default function SharedDocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<SharedDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await listSharedDocuments(0, 100);
      setDocuments(res.items);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;

    setUploading(true);
    let succeeded = 0;
    for (const file of Array.from(files)) {
      try {
        await uploadSharedDocument(file);
        succeeded++;
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Upload failed";
        toast.error(`Failed to upload ${file.name}: ${message}`);
      }
    }
    if (succeeded > 0) {
      toast.success(
        `Uploaded ${succeeded} file${succeeded > 1 ? "s" : ""} successfully`,
      );
      await fetchDocuments();
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDelete = async (doc: SharedDocument) => {
    try {
      await deleteSharedDocument(doc.id);
      toast.success(`Deleted ${doc.filename}`);
      await fetchDocuments();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Delete failed";
      toast.error(message);
    }
  };

  const filtered = searchQuery
    ? documents.filter((d) =>
        d.filename.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : documents;

  const canDelete = (doc: SharedDocument) =>
    user?.role === "admin" || doc.uploaded_by_id === user?.id;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <Breadcrumb />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Shared Documents
          </h1>
          <p className="text-sm text-muted-foreground">
            Upload and share files with your team &middot; {total} file
            {total !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDocuments}
            disabled={loading}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Spinner className="mr-2 h-4 w-4" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            Upload Files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <FolderOpen className="mb-4 h-12 w-12" />
              <p className="text-lg font-medium">
                {searchQuery ? "No matching files" : "No files uploaded yet"}
              </p>
              <p className="text-sm">
                {searchQuery
                  ? "Try a different search term"
                  : "Upload files to share with your team"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">Name</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Uploaded by</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        {fileIcon(doc.content_type)}
                        <div className="min-w-0">
                          <p className="truncate font-medium">
                            {doc.filename}
                          </p>
                          {doc.description && (
                            <p className="truncate text-xs text-muted-foreground">
                              {doc.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {formatBytes(doc.filesize)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {doc.uploaded_by_name || "Unknown"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {timeAgo(doc.created_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" asChild>
                          <a
                            href={getSharedDocumentDownloadUrl(doc.id)}
                            download
                          >
                            <Download className="h-4 w-4" />
                          </a>
                        </Button>
                        {canDelete(doc) && (
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>
                                  Delete file?
                                </AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will permanently delete &quot;{doc.filename}&quot;.
                                  This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => handleDelete(doc)}
                                >
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
