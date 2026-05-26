"use client";
import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/stores";
import type { MessageRatingListResponse, RatingSummary } from "@/types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import Link from "next/link";
import { ExternalLink, Download } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 50;

type RatingFilter = "all" | "positive" | "negative";

export default function AdminRatingsPage() {
  const { user } = useAuthStore();
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [ratings, setRatings] = useState<MessageRatingListResponse | null>(null);
  const [filter, setFilter] = useState<RatingFilter>("all");
  const [commentsOnly, setCommentsOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<"json" | "csv">("csv");

  const fetchRatings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ratingsParams = new URLSearchParams({
        skip: String(page * PAGE_SIZE),
        limit: String(PAGE_SIZE),
        with_comments_only: String(commentsOnly),
      });
      if (filter !== "all") {
        ratingsParams.set("rating_filter", filter === "positive" ? "1" : "-1");
      }

      const [summaryRes, ratingsRes] = await Promise.all([
        fetch("/api/v1/admin/ratings/summary?days=30", {
          credentials: "include",
        }),
        fetch(`/api/v1/admin/ratings?${ratingsParams.toString()}`, {
          credentials: "include",
        }),
      ]);

      if (!summaryRes.ok && !ratingsRes.ok) {
        throw new Error("Failed to fetch ratings data");
      }

      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSummary(summaryData);
      }
      if (ratingsRes.ok) {
        const ratingsData = await ratingsRes.json();
        setRatings(ratingsData);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch ratings";
      setError(errorMessage);
      console.error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [page, filter, commentsOnly]);

  const handleExport = () => {
    const params = new URLSearchParams({
      export_format: exportFormat,
      rating_filter: filter === "all" ? "" : filter === "positive" ? "1" : "-1",
      with_comments_only: commentsOnly.toString(),
    });
    // Remove empty params
    if (!params.get("rating_filter")) params.delete("rating_filter");

    // Note: window.open relies on the browser automatically sending cookies
    // (httpOnly access_token) to the Next.js proxy route for authentication.
    window.open(`/api/v1/admin/ratings/export?${params.toString()}`, "_blank");
  };

  useEffect(() => {
    if (user?.role !== "admin") return;

    fetchRatings();
  }, [user, fetchRatings]);

  if (user?.role !== "admin") {
    return (
      <div className="container mx-auto py-8">
        <div className="text-muted-foreground text-center">{"Access denied"}</div>
      </div>
    );
  }

  if (loading && !summary && !error) {
    return (
      <div className="container mx-auto py-8">
        <h1 className="mb-8 text-3xl font-bold">{"Response Ratings"}</h1>
        {/* Summary Cards Skeleton */}
        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-card rounded-lg border p-4">
              <Skeleton className="mb-2 h-8 w-16" />
              <Skeleton className="h-4 w-24" />
            </div>
          ))}
        </div>
        {/* Chart Skeleton */}
        <div className="bg-card mb-8 rounded-lg border p-6">
          <Skeleton className="mb-4 h-6 w-40" />
          <Skeleton className="h-[300px] w-full" />
        </div>
        {/* Table Skeleton */}
        <div className="bg-card rounded-lg border">
          <div className="border-b p-4">
            <Skeleton className="h-10 w-32" />
          </div>
          <div className="space-y-4 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <h1 className="mb-8 text-3xl font-bold">{"Response Ratings"}</h1>

      {/* Summary Cards */}
      {summary && (
        <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="bg-card rounded-lg border p-4">
            <div className="text-2xl font-bold">{summary.total_ratings}</div>
            <div className="text-muted-foreground text-sm">{"Total Ratings"}</div>
          </div>
          <div className="bg-card rounded-lg border p-4">
            <div className="text-2xl font-bold text-green-600">{summary.like_count}</div>
            <div className="text-muted-foreground text-sm">{"Likes"}</div>
          </div>
          <div className="bg-card rounded-lg border p-4">
            <div className="text-2xl font-bold text-red-600">{summary.dislike_count}</div>
            <div className="text-muted-foreground text-sm">{"Dislikes"}</div>
          </div>
          <div className="bg-card rounded-lg border p-4">
            <div className="text-2xl font-bold">{summary.average_rating.toFixed(2)}</div>
            <div className="text-muted-foreground text-sm">{"Average Rating"}</div>
          </div>
        </div>
      )}

      {/* Chart */}
      {summary && summary.ratings_by_day.length > 0 && (
        <div className="bg-card mb-8 rounded-lg border p-6">
          <h2 className="mb-4 text-xl font-semibold">{"Ratings Over Time"}</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={summary.ratings_by_day}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="likes" fill="#22c55e" name="Likes" />
              <Bar dataKey="dislikes" fill="#ef4444" name="Dislikes" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex items-center gap-4">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as RatingFilter)}
          className="bg-background rounded-md border px-3 py-2"
        >
          <option value="all">{"All Ratings"}</option>
          <option value="positive">{"Likes Only"}</option>
          <option value="negative">{"Dislikes Only"}</option>
        </select>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={commentsOnly}
            onChange={(e) => setCommentsOnly(e.target.checked)}
            className="rounded"
          />
          {"With comments only"}
        </label>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as "json" | "csv")}
            className="bg-background rounded-md border px-3 py-2"
          >
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
          </select>
          <button
            onClick={handleExport}
            className="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex items-center gap-2 rounded-md px-3 py-2"
          >
            <Download className="h-4 w-4" />
            {"Export"}
          </button>
        </div>
      </div>

      {/* Ratings List */}
      <div className="bg-card rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-b">
              <th className="p-4 text-left">{"Date"}</th>
              <th className="p-4 text-left">{"Rating"}</th>
              <th className="p-4 text-left">{"Comment"}</th>
              <th className="p-4 text-left">{"Message"}</th>
              <th className="p-4 text-left">{"User"}</th>
              <th className="p-4 text-left">{"Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {ratings?.items.map((rating) => (
              <tr key={rating.id} className="hover:bg-muted/50 border-b">
                <td className="p-4">{formatDate(rating.created_at)}</td>
                <td className="p-4">
                  {rating.rating === 1 ? (
                    <span className="text-green-600">👍 Like</span>
                  ) : (
                    <span className="text-red-600">👎 Dislike</span>
                  )}
                </td>
                <td className="max-w-md truncate p-4">{rating.comment || "-"}</td>
                <td className="text-muted-foreground max-w-xs truncate p-4">
                  {rating.message_content || "-"}
                </td>
                <td className="p-4">{rating.user_name || rating.user_email || "-"}</td>
                <td className="p-4">
                  {rating.conversation_id && (
                    <Link
                      href={`/chat?id=${rating.conversation_id}`}
                      className="text-primary inline-flex items-center gap-1 text-sm hover:underline"
                    >
                      {"View conversation"}
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {loading && ratings && (
              <tr>
                <td colSpan={6} className="p-4">
                  <div className="flex justify-center">
                    <div className="border-primary h-6 w-6 animate-spin rounded-full border-b-2"></div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {ratings && ratings.total > PAGE_SIZE && (
          <div className="flex justify-center gap-2 border-t p-4">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="hover:bg-muted rounded px-3 py-1 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="px-3 py-1">
              Page {page + 1} of {Math.ceil(ratings.total / PAGE_SIZE)}
            </span>
            <button
              onClick={() => setPage(Math.min(Math.ceil(ratings.total / PAGE_SIZE) - 1, page + 1))}
              disabled={page >= Math.ceil(ratings.total / PAGE_SIZE) - 1}
              className="hover:bg-muted rounded px-3 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
