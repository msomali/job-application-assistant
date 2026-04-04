import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { toast } from "sonner";
import { Download, Plus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { QueryState } from "@/components/shared/query-state";
import { JsonImportDialog } from "@/components/profile/json-import-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

interface ProfileFormData {
  full_name: string;
  contact: {
    email: string;
    phone: string;
    linkedin: string;
    github: string;
    website: string;
  };
  summary: string;
  experience: { company: string; title: string; dates: string; bullets: string[] }[];
  education: { school: string; degree: string; dates: string }[];
  skills: string;
  certifications: string;
}

function buildFormValues(p: any): ProfileFormData {
  return {
    full_name: p?.full_name ?? "",
    contact: {
      email: p?.contact?.email ?? "",
      phone: p?.contact?.phone ?? "",
      linkedin: p?.contact?.linkedin ?? "",
      github: p?.contact?.github ?? "",
      website: p?.contact?.website ?? "",
    },
    summary: p?.summary ?? "",
    experience: (p?.experience ?? []).map((e: any) => ({
      company: e.company ?? "",
      title: e.title ?? "",
      dates: e.dates ?? "",
      bullets: e.bullets ?? [],
    })),
    education: (p?.education ?? []).map((e: any) => ({
      school: e.school ?? "",
      degree: e.degree ?? "",
      dates: e.dates ?? "",
    })),
    skills: (p?.skills ?? []).join(", "),
    certifications: (p?.certifications ?? []).join(", "),
  };
}

function ProfileForm({ initialData }: { initialData: any }) {
  const queryClient = useQueryClient();
  const [importOpen, setImportOpen] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (data: any) => apiClient.put("/api/profile", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Profile saved");
      queryClient.invalidateQueries({ queryKey: queryKeys.profile.current });
    },
    onError: () => toast.error("Failed to save profile"),
  });

  const importMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/profile/import", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Profile imported");
      setImportOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.profile.current });
    },
    onError: () => toast.error("Failed to import profile"),
  });

  const form = useForm<ProfileFormData>({
    defaultValues: buildFormValues(initialData),
  });

  const expArray = useFieldArray({ control: form.control, name: "experience" });
  const eduArray = useFieldArray({ control: form.control, name: "education" });

  useEffect(() => {
    form.reset(buildFormValues(initialData));
  }, [initialData, form]);

  const onSubmit = form.handleSubmit((data) => {
    updateMutation.mutate({
      full_name: data.full_name || null,
      contact: data.contact,
      summary: data.summary || null,
      experience: data.experience,
      education: data.education,
      skills: data.skills
        ? data.skills
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      certifications: data.certifications
        ? data.certifications
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    });
  });

  async function handleExport() {
    try {
      const resp = await apiClient.get("/api/profile/export");
      const blob = new Blob([JSON.stringify(resp.data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "master_resume.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to export profile");
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="flex items-center gap-2">
        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? "Saving..." : "Save"}
        </Button>
        <Button type="button" variant="outline" onClick={() => setImportOpen(true)}>
          <Upload className="mr-1.5 h-4 w-4" /> Import JSON
        </Button>
        <Button type="button" variant="outline" onClick={handleExport}>
          <Download className="mr-1.5 h-4 w-4" /> Export JSON
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Contact Info</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="col-span-2 space-y-1">
            <Label>Full Name</Label>
            <Input {...form.register("full_name")} />
          </div>
          <div className="space-y-1">
            <Label>Email</Label>
            <Input {...form.register("contact.email")} />
          </div>
          <div className="space-y-1">
            <Label>Phone</Label>
            <Input {...form.register("contact.phone")} />
          </div>
          <div className="space-y-1">
            <Label>LinkedIn</Label>
            <Input {...form.register("contact.linkedin")} />
          </div>
          <div className="space-y-1">
            <Label>GitHub</Label>
            <Input {...form.register("contact.github")} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Professional Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea rows={4} {...form.register("summary")} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Work Experience</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              expArray.append({ company: "", title: "", dates: "", bullets: [] })
            }
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Add
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {expArray.fields.map((field, i) => (
            <div key={field.id} className="space-y-2 rounded border p-3">
              <div className="flex gap-2">
                <div className="flex-1 space-y-1">
                  <Label>Company</Label>
                  <Input {...form.register(`experience.${i}.company`)} />
                </div>
                <div className="flex-1 space-y-1">
                  <Label>Title</Label>
                  <Input {...form.register(`experience.${i}.title`)} />
                </div>
                <div className="w-40 space-y-1">
                  <Label>Dates</Label>
                  <Input {...form.register(`experience.${i}.dates`)} />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="mt-6"
                  onClick={() => expArray.remove(i)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </div>
          ))}
          {expArray.fields.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No experience entries. Click "Add" to start.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Education</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => eduArray.append({ school: "", degree: "", dates: "" })}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Add
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {eduArray.fields.map((field, i) => (
            <div key={field.id} className="flex gap-2">
              <div className="flex-1 space-y-1">
                <Label>School</Label>
                <Input {...form.register(`education.${i}.school`)} />
              </div>
              <div className="flex-1 space-y-1">
                <Label>Degree</Label>
                <Input {...form.register(`education.${i}.degree`)} />
              </div>
              <div className="w-40 space-y-1">
                <Label>Dates</Label>
                <Input {...form.register(`education.${i}.dates`)} />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="mt-6"
                onClick={() => eduArray.remove(i)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Skills & Certifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label>Skills (comma-separated)</Label>
            <Input
              {...form.register("skills")}
              placeholder="Python, FastAPI, PostgreSQL, ..."
            />
          </div>
          <div className="space-y-1">
            <Label>Certifications (comma-separated)</Label>
            <Input
              {...form.register("certifications")}
              placeholder="AWS Solutions Architect, ..."
            />
          </div>
        </CardContent>
      </Card>

      <JsonImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImport={(data) => importMutation.mutate(data)}
        isPending={importMutation.isPending}
      />
    </form>
  );
}

export function Component() {
  const profileQuery = useQuery({
    queryKey: queryKeys.profile.current,
    queryFn: () => apiClient.get("/api/profile").then((r) => r.data),
    staleTime: 300_000,
  });

  return (
    <QueryState
      query={profileQuery}
      empty={<ProfileForm initialData={null} />}
    >
      {(data) => <ProfileForm initialData={data} />}
    </QueryState>
  );
}
