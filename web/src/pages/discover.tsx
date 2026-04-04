import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { QueryState } from "@/components/shared/query-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

interface ConfigFormData {
  name: string;
  config_type: string;
  query?: string;
  location?: string;
  url?: string;
}

export function Component() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const configsQuery = useQuery({
    queryKey: queryKeys.discovery.configs,
    queryFn: () => apiClient.get("/api/discovery/configs").then((r) => r.data),
  });

  const runMutation = useMutation({
    mutationFn: () => apiClient.post("/api/discovery/run").then((r) => r.data),
    onSuccess: () => toast.success("Discovery started"),
    onError: () => toast.error("Failed to start discovery"),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => apiClient.post("/api/discovery/configs", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Config created");
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to create config"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: any) =>
      apiClient.put(`/api/discovery/configs/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Config updated");
      setFormOpen(false);
      setEditId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to update config"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/discovery/configs/${id}`),
    onSuccess: () => {
      toast.success("Config deleted");
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to delete config"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      apiClient.put(`/api/discovery/configs/${id}`, { is_active }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs }),
  });

  const form = useForm<ConfigFormData>({
    defaultValues: { name: "", config_type: "search_query", query: "", location: "", url: "" },
  });

  function openCreate() {
    form.reset({ name: "", config_type: "search_query", query: "", location: "", url: "" });
    setEditId(null);
    setFormOpen(true);
  }

  function openEdit(config: any) {
    form.reset({
      name: config.name,
      config_type: config.config_type,
      query: config.config?.query ?? "",
      location: config.config?.location ?? "",
      url: config.config?.url ?? "",
    });
    setEditId(config.id);
    setFormOpen(true);
  }

  function handleSubmit(data: ConfigFormData) {
    const payload = {
      name: data.name,
      config_type: data.config_type,
      config:
        data.config_type === "search_query"
          ? { query: data.query, location: data.location }
          : { url: data.url },
    };
    if (editId) {
      updateMutation.mutate({ id: editId, ...payload });
    } else {
      createMutation.mutate(payload);
    }
  }

  const configs = (configsQuery.data ?? []) as any[];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" /> Add Config
        </Button>
        <Button variant="outline" onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
          {runMutation.isPending ? "Running..." : "Run All"}
        </Button>
      </div>

      <QueryState
        query={configsQuery}
        isEmpty={(data: any[]) => data.length === 0}
        empty={<p className="text-sm text-muted-foreground">No search configs yet. Create one to start discovering jobs.</p>}
      >
        {(data: any[]) => (
          <div className="grid grid-cols-2 gap-3">
            {data.map((config: any) => (
              <Card key={config.id}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm">{config.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={config.is_active}
                      onCheckedChange={(checked: boolean) =>
                        toggleMutation.mutate({ id: config.id, is_active: checked })
                      }
                    />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(config)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteId(config.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  <p>Type: {config.config_type}</p>
                  <p>Config: {JSON.stringify(config.config)}</p>
                  {config.last_run_at && <p>Last run: {timeAgo(config.last_run_at)}</p>}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </QueryState>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editId ? "Edit Config" : "New Config"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label>Name</Label>
              <Input {...form.register("name")} />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Select
                value={form.watch("config_type")}
                onValueChange={(v: string) => form.setValue("config_type", v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="search_query">Search Query</SelectItem>
                  <SelectItem value="career_page">Career Page</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.watch("config_type") === "search_query" ? (
              <>
                <div className="space-y-1"><Label>Query</Label><Input {...form.register("query")} /></div>
                <div className="space-y-1"><Label>Location</Label><Input {...form.register("location")} /></div>
              </>
            ) : (
              <div className="space-y-1"><Label>Career page URL</Label><Input {...form.register("url")} /></div>
            )}
            <DialogFooter>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {editId ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={() => setDeleteId(null)}
        title="Delete config"
        description="Are you sure you want to delete this search config?"
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
