import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const invoicesQuery = useQuery({
    queryKey: queryKeys.billing.invoices,
    queryFn: () => apiClient.get("/api/billing/invoices").then((r) => r.data),
    staleTime: 600_000,
  });

  return (
    <div className="max-w-2xl">
      <Card>
        <CardHeader><CardTitle className="text-base">Invoice History</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={invoicesQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={
              <p className="text-sm text-muted-foreground">
                No invoices yet. Invoice history will appear here once billing is active.
              </p>
            }
          >
            {(data: any[]) => (
              <div>
                {data.map((inv: any, i: number) => (
                  <div key={i} className="flex items-center justify-between border-b py-2 text-sm last:border-0">
                    <span>{inv.date}</span>
                    <span>{inv.amount}</span>
                    <span>{inv.status}</span>
                  </div>
                ))}
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
