import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from "@/api/client";

export function Component() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState<"indeed" | "linkedin">("indeed");

  const searchMutation = useMutation({
    mutationFn: () =>
      apiClient
        .post(`/api/search/${source}`, {
          query,
          location: location || undefined,
          limit: 10,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Search started (task ${data.id.slice(0, 8)}...)`);
    },
    onError: () => toast.error("Search failed"),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Input
          className="flex-1"
          placeholder="Search for jobs..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) searchMutation.mutate();
          }}
        />
        <Input
          className="w-48"
          placeholder="Location (optional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <Select value={source} onValueChange={(v: string | null) => setSource((v ?? "indeed") as "indeed" | "linkedin")}>
          <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="indeed">Indeed</SelectItem>
            <SelectItem value="linkedin">LinkedIn</SelectItem>
          </SelectContent>
        </Select>
        <Button
          onClick={() => query.trim() && searchMutation.mutate()}
          disabled={searchMutation.isPending || !query.trim()}
        >
          <Search className="mr-1.5 h-4 w-4" />
          {searchMutation.isPending ? "Searching..." : "Search"}
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        Search results will appear in your Jobs list once discovered. Check the task indicator in the top bar for progress.
      </p>
    </div>
  );
}
