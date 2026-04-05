import { useQuery, useMutation } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { SkillTag } from "@/components/jobs/skill-tag";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = Number(id);

  const jobQuery = useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}`).then((r) => r.data),
  });

  const analysisQuery = useQuery({
    queryKey: queryKeys.analysis.byJob(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}/analysis`).then((r) => r.data),
    retry: false,
  });

  const docsQuery = useQuery({
    queryKey: queryKeys.documents.byJob(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}/documents`).then((r) => r.data),
  });

  const analyzeMutation = useMutation({
    mutationFn: () => apiClient.post(`/api/jobs/${jobId}/analyze`).then((r) => r.data),
    onSuccess: () => toast.success("Analysis started"),
    onError: () => toast.error("Failed to start analysis"),
  });

  const generateMutation = useMutation({
    mutationFn: () => apiClient.post(`/api/jobs/${jobId}/generate`).then((r) => r.data),
    onSuccess: () => toast.success("Document generation started"),
    onError: () => toast.error("Failed to start generation"),
  });

  return (
    <QueryState query={jobQuery}>
      {(job: any) => {
        const analysis = analysisQuery.data as any;
        const docs = docsQuery.data as any;

        return (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" className="h-auto p-0 text-xs" onClick={() => navigate("/jobs")}>
              <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Jobs
            </Button>

            <div className="flex flex-col gap-5 md:flex-row">
              <div className="min-w-0 flex-1 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold">{job.title}</h2>
                    <p className="text-sm text-muted-foreground">
                      {job.company}
                      {job.location && ` · ${job.location}`}
                      {job.job_type && ` · ${job.job_type}`}
                      {job.salary_range && ` · ${job.salary_range}`}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Scraped {timeAgo(job.scraped_at)}
                      {job.application_url && (
                        <>
                          {" · "}
                          <a
                            href={job.application_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-primary hover:underline"
                          >
                            Original <ExternalLink className="h-3 w-3" />
                          </a>
                        </>
                      )}
                    </p>
                  </div>
                  {analysis && <ScoreBadge score={analysis.fit_score} size="lg" />}
                </div>

                <Tabs defaultValue="analysis">
                  <TabsList>
                    <TabsTrigger value="analysis">Analysis</TabsTrigger>
                    <TabsTrigger value="description">Description</TabsTrigger>
                    <TabsTrigger value="documents">Documents</TabsTrigger>
                  </TabsList>

                  <TabsContent value="analysis" className="space-y-4 pt-2">
                    {analysisQuery.isLoading ? (
                      <p className="text-sm text-muted-foreground">Loading analysis...</p>
                    ) : analysis ? (
                      <>
                        <Card>
                          <CardContent className="space-y-2 pt-4 text-sm">
                            <h3 className="font-semibold">Score Breakdown</h3>
                            <div className="flex gap-2">
                              <span className="w-32 text-muted-foreground">Base score:</span>
                              <span>{analysis.base_score ?? "—"}</span>
                            </div>
                            {(analysis.penalties ?? []).map((p: any, i: number) => (
                              <div key={i} className="flex gap-2">
                                <span className="w-32 text-muted-foreground">{p.reason ?? `Penalty ${i + 1}`}:</span>
                                <span className="text-red-600">{p.adjustment ?? p.value ?? "—"}</span>
                              </div>
                            ))}
                            <div className="flex gap-2 border-t pt-2 font-semibold">
                              <span className="w-32">Final score:</span>
                              <span className="text-green-600">{analysis.fit_score}</span>
                            </div>
                          </CardContent>
                        </Card>

                        <Card>
                          <CardContent className="pt-4">
                            <h3 className="mb-2 text-sm font-semibold">Skills</h3>
                            <div className="flex flex-wrap gap-1.5">
                              {(analysis.matching_skills ?? []).map((s: string) => (
                                <SkillTag key={s} name={s} variant="match" />
                              ))}
                              {(analysis.gaps ?? []).map((s: string) => (
                                <SkillTag key={s} name={s} variant="gap" />
                              ))}
                            </div>
                          </CardContent>
                        </Card>

                        {analysis.fit_reasoning && (
                          <Card>
                            <CardContent className="pt-4">
                              <h3 className="mb-2 text-sm font-semibold">Recommendation</h3>
                              <p className="text-sm leading-relaxed text-muted-foreground">
                                {analysis.fit_reasoning}
                              </p>
                            </CardContent>
                          </Card>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No analysis yet. Click "Analyze" to start.
                      </p>
                    )}
                  </TabsContent>

                  <TabsContent value="description" className="pt-2">
                    <Card>
                      <CardContent className="pt-4">
                        <div className="prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap">
                          {job.description || "No description available."}
                        </div>
                      </CardContent>
                    </Card>
                  </TabsContent>

                  <TabsContent value="documents" className="pt-2">
                    <Card>
                      <CardContent className="pt-4 space-y-2">
                        {docs?.resume_url ? (
                          <a
                            href={docs.resume_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 rounded border p-2 text-sm hover:bg-muted/40"
                          >
                            <Download className="h-4 w-4" /> Resume PDF
                          </a>
                        ) : null}
                        {docs?.cover_letter_url ? (
                          <a
                            href={docs.cover_letter_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 rounded border p-2 text-sm hover:bg-muted/40"
                          >
                            <Download className="h-4 w-4" /> Cover Letter PDF
                          </a>
                        ) : null}
                        {!docs?.resume_url && !docs?.cover_letter_url && (
                          <p className="text-sm text-muted-foreground">
                            No documents generated yet. Click "Generate" to create tailored docs.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                </Tabs>
              </div>

              <div className="w-full md:w-64 shrink-0 space-y-3">
                <h3 className="text-sm font-semibold">Actions</h3>
                <Button
                  className="w-full"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  Generate Resume
                </Button>
                <Button
                  className="w-full"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  Generate Cover Letter
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => analyzeMutation.mutate()}
                  disabled={analyzeMutation.isPending}
                >
                  {analysisQuery.data ? "Re-analyze" : "Analyze"}
                </Button>
              </div>
            </div>
          </div>
        );
      }}
    </QueryState>
  );
}
