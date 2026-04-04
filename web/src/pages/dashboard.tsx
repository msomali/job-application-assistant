import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

export function Component() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [scrapeUrl, setScrapeUrl] = useState("");

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 100 }),
    queryFn: () => apiClient.get("/api/jobs?limit=100").then((r) => r.data),
    staleTime: 30_000,
  });

  const rankedQuery = useQuery({
    queryKey: queryKeys.jobs.ranked(5),
    queryFn: () => apiClient.get("/api/jobs/ranked?limit=5").then((r) => r.data),
    staleTime: 30_000,
  });

  const skillGapsQuery = useQuery({
    queryKey: queryKeys.skills.gaps,
    queryFn: () => apiClient.get("/api/skills/gaps").then((r) => r.data),
    staleTime: 120_000,
  });

  const scrapeMutation = useMutation({
    mutationFn: (url: string) =>
      apiClient.post("/api/jobs/scrape", { url }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Scrape task started");
      setScrapeUrl("");
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    },
    onError: () => toast.error("Failed to start scrape"),
  });

  const discoveryMutation = useMutation({
    mutationFn: () => apiClient.post("/api/discovery/run").then((r) => r.data),
    onSuccess: () => toast.success("Discovery started"),
    onError: () => toast.error("Failed to start discovery"),
  });

  const jobs = (jobsQuery.data ?? []) as any[];
  const ranked = (rankedQuery.data ?? []) as any[];
  const gaps = (skillGapsQuery.data ?? []) as any[];
  const totalJobs = jobs.length;
  const topGap = gaps[0]?.skill ?? "—";
  const topGapCount = gaps[0]?.demand_count ?? 0;

  return (
    <div className="space-y-5">
      {/* Quick action bar */}
      <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3.5">
        <Input
          className="flex-1"
          placeholder="Paste a job URL to scrape..."
          value={scrapeUrl}
          onChange={(e) => setScrapeUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && scrapeUrl.trim()) {
              scrapeMutation.mutate(scrapeUrl.trim());
            }
          }}
        />
        <Button
          onClick={() => scrapeUrl.trim() && scrapeMutation.mutate(scrapeUrl.trim())}
          disabled={scrapeMutation.isPending || !scrapeUrl.trim()}
        >
          Scrape Job
        </Button>
        <Button
          variant="outline"
          onClick={() => discoveryMutation.mutate()}
          disabled={discoveryMutation.isPending}
        >
          Run Discovery
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Total Jobs</div>
            <div className="text-3xl font-bold">{totalJobs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Avg Fit Score</div>
            <div className="text-3xl font-bold">—</div>
            <div className="mt-1.5 h-1 rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: "0%" }} />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Docs Generated</div>
            <div className="text-3xl font-bold">—</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Top Skill Gap</div>
            <div className="mt-1 text-lg font-semibold text-amber-600">{topGap}</div>
            {topGapCount > 0 && (
              <div className="text-[11px] text-muted-foreground">in {topGapCount} job listings</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top ranked jobs */}
      <Card>
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">Top Ranked Jobs</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => navigate("/jobs")}>
            View all →
          </Button>
        </div>
        <QueryState
          query={rankedQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={<p className="p-4 text-sm text-muted-foreground">No analyzed jobs yet. Scrape a job URL above to get started.</p>}
        >
          {(data: any[]) => (
            <div>
              {data.map((job: any) => (
                <div
                  key={job.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-4 py-2.5 text-sm last:border-0 hover:bg-muted/40"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  <ScoreBadge score={job.fit_score ?? null} />
                  <span className="font-medium">{job.title}</span>
                  <span className="text-muted-foreground">{job.company}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{timeAgo(job.scraped_at)}</span>
                </div>
              ))}
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
