import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { QueryState } from "@/components/shared/query-state";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { useAuthStore } from "@/stores/auth-store";
import { useState } from "react";

export function Component() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === "owner" || user?.role === "admin";

  return (
    <div className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle className="text-base">Account</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Email</span>
            <span>{user?.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Role</span>
            <Badge variant="outline">{user?.role}</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Appearance</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <span>Theme</span>
            <ThemeToggle />
          </div>
        </CardContent>
      </Card>

      {isAdmin && <TeamSection />}
    </div>
  );
}

function TeamSection() {
  const queryClient = useQueryClient();
  const [removeTarget, setRemoveTarget] = useState<{ id: string; email: string } | null>(null);

  const usersQuery = useQuery({
    queryKey: queryKeys.admin.users,
    queryFn: () => apiClient.get("/api/admin/users").then((r) => r.data),
  });

  const changeRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      apiClient.put(`/api/admin/users/${userId}/role`, null, { params: { role } }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Role updated");
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
    },
    onError: () => toast.error("Failed to update role"),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => apiClient.delete(`/api/admin/users/${userId}`),
    onSuccess: () => {
      toast.success("User removed");
      setRemoveTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Failed to remove user"),
  });

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Team Members</CardTitle></CardHeader>
      <CardContent>
        <QueryState query={usersQuery} isEmpty={(data: any[]) => data.length === 0}>
          {(data: any[]) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((u: any) => (
                  <TableRow key={u.id}>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        onValueChange={(role: string) => changeRoleMutation.mutate({ userId: u.id, role })}
                      >
                        <SelectTrigger className="w-28 h-8"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="owner">Owner</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="member">Member</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-destructive"
                        onClick={() => setRemoveTarget({ id: u.id, email: u.email })}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </CardContent>

      <ConfirmDialog
        open={!!removeTarget}
        onOpenChange={() => setRemoveTarget(null)}
        title="Remove user"
        description={`Remove ${removeTarget?.email} from the team?`}
        confirmLabel="Remove"
        variant="destructive"
        onConfirm={() => removeTarget && removeMutation.mutate(removeTarget.id)}
        isPending={removeMutation.isPending}
      />
    </Card>
  );
}
