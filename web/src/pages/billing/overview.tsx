import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const navigate = useNavigate();

  const planQuery = useQuery({
    queryKey: queryKeys.billing.plan,
    queryFn: () => apiClient.get("/api/billing/plan").then((r) => r.data),
    staleTime: 600_000,
  });

  const usageQuery = useQuery({
    queryKey: queryKeys.billing.usage,
    queryFn: () => apiClient.get("/api/billing/usage").then((r) => r.data),
    staleTime: 60_000,
  });

  return (
    <div className="max-w-2xl space-y-5">
      <QueryState query={planQuery}>
        {(plan: any) => (
          <Card>
            <CardHeader><CardTitle className="text-base">Current Plan</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold capitalize">{plan.plan}</span>
                <Button variant="outline" onClick={() => navigate("/billing/plans")}>View Plans</Button>
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>Scrapes: {plan.limits.scrapes_per_day}/day</p>
                <p>Analyses: {plan.limits.analyses_per_day}/day</p>
                <p>Generations: {plan.limits.generations_per_day}/day</p>
              </div>
            </CardContent>
          </Card>
        )}
      </QueryState>

      <QueryState query={usageQuery}>
        {(usage: any) => (
          <Card>
            <CardHeader><CardTitle className="text-base">Current Period Usage</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {Object.entries(usage.actions ?? {}).map(([action, count]: [string, any]) => (
                <div key={action} className="flex items-center justify-between">
                  <span className="capitalize">{action}</span>
                  <span className="font-mono">{count}</span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t pt-2">
                <span>Total tokens</span>
                <span className="font-mono">{usage.tokens_used?.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>
        )}
      </QueryState>

      <div className="flex gap-2">
        <Button variant="outline" onClick={() => navigate("/billing/usage")}>Detailed Usage</Button>
        <Button variant="outline" onClick={() => navigate("/billing/history")}>Invoice History</Button>
      </div>
    </div>
  );
}
