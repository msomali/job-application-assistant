import { type UseQueryResult } from "@tanstack/react-query";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  loading?: React.ReactNode;
  empty?: React.ReactNode;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}

export function QueryState<T>({
  query,
  loading,
  empty,
  isEmpty,
  children,
}: QueryStateProps<T>) {
  if (query.isLoading) {
    return <>{loading ?? <DefaultLoading />}</>;
  }

  if (query.isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {query.error instanceof Error ? query.error.message : "Something went wrong"}
        </p>
        <Button variant="outline" size="sm" onClick={() => query.refetch()}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" /> Retry
        </Button>
      </div>
    );
  }

  if (query.data === undefined || query.data === null) {
    return <>{empty ?? null}</>;
  }

  if (isEmpty?.(query.data)) {
    return <>{empty ?? null}</>;
  }

  return <>{children(query.data)}</>;
}

function DefaultLoading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
