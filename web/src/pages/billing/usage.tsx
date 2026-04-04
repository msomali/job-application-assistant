import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const historyQuery = useQuery({
    queryKey: queryKeys.billing.history(30),
    queryFn: () => apiClient.get("/api/billing/usage/history?days=30").then((r) => r.data),
    staleTime: 60_000,
  });

  return (
    <div className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle className="text-base">Daily Usage (Last 30 Days)</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={historyQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No usage data yet.</p>}
          >
            {(data: any[]) => {
              const dayMap = new Map<string, number>();
              for (const d of data) {
                const day = d.day.slice(0, 10);
                dayMap.set(day, (dayMap.get(day) ?? 0) + d.count);
              }
              const chartData = Array.from(dayMap.entries())
                .map(([day, count]) => ({ day, count }))
                .sort((a, b) => a.day.localeCompare(b.day));

              return (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              );
            }}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
