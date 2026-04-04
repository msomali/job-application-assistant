import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Plus, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { QueryState } from "@/components/shared/query-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { useDebounce } from "@/hooks/use-debounce";

interface AnswerFormData {
  question: string;
  answer: string;
  category: string;
}

export function Component() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<any | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const answersQuery = useQuery({
    queryKey: queryKeys.answers.list({ search: debouncedSearch }),
    queryFn: () => {
      const qs = new URLSearchParams();
      if (debouncedSearch) qs.set("search", debouncedSearch);
      return apiClient.get(`/api/answers?${qs}`).then((r) => r.data);
    },
  });

  const statsQuery = useQuery({
    queryKey: queryKeys.answers.stats,
    queryFn: () => apiClient.get("/api/answers/stats").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: AnswerFormData) =>
      apiClient.post("/api/answers", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Answer added");
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to add answer"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: number; answer?: string; category?: string }) =>
      apiClient.put(`/api/answers/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Answer updated");
      setFormOpen(false);
      setEditTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to update answer"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/answers/${id}`),
    onSuccess: () => {
      toast.success("Answer deleted");
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to delete answer"),
  });

  const importMutation = useMutation({
    mutationFn: (data: any[]) => apiClient.post("/api/answers/import", data).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Imported ${data.imported} answers`);
      setImportOpen(false);
      setImportText("");
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Import failed"),
  });

  const form = useForm<AnswerFormData>({
    defaultValues: { question: "", answer: "", category: "" },
  });

  function openCreate() {
    form.reset({ question: "", answer: "", category: "" });
    setEditTarget(null);
    setFormOpen(true);
  }

  function openEdit(a: any) {
    form.reset({ question: a.question, answer: a.answer, category: a.category ?? "" });
    setEditTarget(a);
    setFormOpen(true);
  }

  function handleSubmit(data: AnswerFormData) {
    if (editTarget) {
      updateMutation.mutate({
        id: editTarget.id,
        answer: data.answer,
        category: data.category || undefined,
      });
    } else {
      createMutation.mutate(data);
    }
  }

  function handleImport() {
    try {
      const data = JSON.parse(importText);
      if (!Array.isArray(data)) {
        toast.error("JSON must be an array");
        return;
      }
      importMutation.mutate(data);
    } catch {
      toast.error("Invalid JSON");
    }
  }

  const stats = statsQuery.data as any;

  return (
    <div className="space-y-5">
      {stats && (
        <div className="flex gap-3">
          <Card className="flex-1">
            <CardContent className="pt-4">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">Total Answers</div>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="pt-4">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">Used at Least Once</div>
              <div className="text-2xl font-bold">{stats.used}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex items-center gap-3">
        <Input className="w-64" placeholder="Search answers..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="ml-auto flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="mr-1.5 h-4 w-4" /> Import
          </Button>
          <Button onClick={openCreate}>
            <Plus className="mr-1.5 h-4 w-4" /> Add Answer
          </Button>
        </div>
      </div>

      <div className="rounded-lg border">
        <QueryState
          query={answersQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={<p className="p-8 text-center text-sm text-muted-foreground">No answers yet.</p>}
        >
          {(data: any[]) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Answer</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Used</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((a: any) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-xs truncate font-medium">{a.question}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">{a.answer}</TableCell>
                    <TableCell>{a.category ?? "—"}</TableCell>
                    <TableCell className="text-right">{a.times_used}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEdit(a)}>Edit</Button>
                      <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive" onClick={() => setDeleteId(a.id)}>Delete</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </div>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editTarget ? "Edit Answer" : "Add Answer"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label>Question</Label>
              <Input {...form.register("question")} disabled={!!editTarget} />
            </div>
            <div className="space-y-1">
              <Label>Answer</Label>
              <Textarea rows={4} {...form.register("answer")} />
            </div>
            <div className="space-y-1">
              <Label>Category (optional)</Label>
              <Input {...form.register("category")} />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {editTarget ? "Update" : "Add"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Import Answers</DialogTitle></DialogHeader>
          <Textarea
            rows={10}
            placeholder='[{"question": "...", "answer": "...", "category": "..."}]'
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            className="font-mono text-xs"
          />
          <DialogFooter>
            <Button onClick={handleImport} disabled={importMutation.isPending || !importText.trim()}>
              {importMutation.isPending ? "Importing..." : "Import"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={() => setDeleteId(null)}
        title="Delete answer"
        description="Are you sure you want to delete this answer?"
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
