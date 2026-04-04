import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { SkillTag } from "@/components/jobs/skill-tag";
import { QueryState } from "@/components/shared/query-state";
import { Pagination } from "@/components/shared/pagination";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-debounce";

const PAGE_SIZE = 20;

type SortBy = "scraped_at" | "title" | "company";

export function Component() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("scraped_at");
  const [scrapeOpen, setScrapeOpen] = useState(false);
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; title: string } | null>(null);

  const debouncedSearch = useDebounce(search, 300);

  const params = {
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    sort_by: sortBy,
    order: "desc" as const,
    ...(debouncedSearch ? { search: debouncedSearch } : {}),
  };

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => {
      const qs = new URLSearchParams();
      qs.set("offset", String(params.offset));
      qs.set("limit", String(params.limit));
      qs.set("sort_by", params.sort_by);
      qs.set("order", params.order);
      if (params.search) qs.set("search", params.search);
      return apiClient.get(`/api/jobs?${qs}`).then((r) => r.data);
    },
    staleTime: 30_000,
  });

  const scrapeMutation = useMutation({
    mutationFn: (url: string) =>
      apiClient.post("/api/jobs/scrape", { url }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Scrape task started");
      setScrapeOpen(false);
      setScrapeUrl("");
    },
    onError: () => toast.error("Failed to start scrape"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/jobs/${id}`),
    onSuccess: () => {
      toast.success("Job deleted");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
    onError: () => toast.error("Failed to delete job"),
  });

  const jobs = (jobsQuery.data ?? []) as any[];

  // Suppress unused variable warning
  void jobs;
  void SkillTag;

  return (
    <div className="space-y-0">
      {/* Toolbar */}
      <div className="flex items-center gap-3 pb-4">
        <Input
          className="w-64"
          placeholder="Search jobs..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
        />
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
        >
          <option value="scraped_at">Sort: Date</option>
          <option value="title">Sort: Title</option>
          <option value="company">Sort: Company</option>
        </select>
        <div className="ml-auto">
          <Button size="sm" onClick={() => setScrapeOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Scrape URL
          </Button>
        </div>
      </div>

      {/* Job list */}
      <div className="rounded-lg border">
        <QueryState
          query={jobsQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={
            <p className="p-8 text-center text-sm text-muted-foreground">
              No jobs yet. Click "Scrape URL" to add your first job.
            </p>
          }
        >
          {(data: any[]) => (
            <>
              {data.map((job: any) => (
                <div
                  key={job.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-4 py-3 text-sm last:border-0 hover:bg-muted/40"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  <ScoreBadge score={null} />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold">{job.title}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {job.company}
                      {job.location && ` · ${job.location}`}
                      {job.salary_range && ` · ${job.salary_range}`}
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground">{timeAgo(job.scraped_at)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget({ id: job.id, title: job.title });
                    }}
                  >
                    Delete
                  </Button>
                </div>
              ))}
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={data.length < PAGE_SIZE ? page * PAGE_SIZE + data.length : (page + 1) * PAGE_SIZE + 1}
                onChange={setPage}
              />
            </>
          )}
        </QueryState>
      </div>

      {/* Scrape dialog */}
      <Dialog open={scrapeOpen} onOpenChange={setScrapeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Scrape a job URL</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="https://..."
            value={scrapeUrl}
            onChange={(e) => setScrapeUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && scrapeUrl.trim()) {
                scrapeMutation.mutate(scrapeUrl.trim());
              }
            }}
          />
          <DialogFooter>
            <Button
              onClick={() => scrapeUrl.trim() && scrapeMutation.mutate(scrapeUrl.trim())}
              disabled={scrapeMutation.isPending || !scrapeUrl.trim()}
            >
              {scrapeMutation.isPending ? "Starting..." : "Scrape"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={() => setDeleteTarget(null)}
        title="Delete job"
        description={`Are you sure you want to delete "${deleteTarget?.title}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
