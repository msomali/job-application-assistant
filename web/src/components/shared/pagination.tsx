import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t px-5 py-2.5 text-xs text-muted-foreground">
      <span>
        Showing {start}–{end} of {total}
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          disabled={page === 0}
          onClick={() => onChange(page - 1)}
        >
          Prev
        </Button>
        {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
          const pageNum = page <= 2 ? i : page - 2 + i;
          if (pageNum >= totalPages) return null;
          return (
            <Button
              key={pageNum}
              variant={pageNum === page ? "default" : "outline"}
              size="sm"
              className="h-7 w-7 text-xs p-0"
              onClick={() => onChange(pageNum)}
            >
              {pageNum + 1}
            </Button>
          );
        })}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          disabled={page >= totalPages - 1}
          onClick={() => onChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
