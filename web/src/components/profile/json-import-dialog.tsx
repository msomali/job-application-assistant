import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

interface JsonImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (data: Record<string, unknown>) => void;
  isPending?: boolean;
}

export function JsonImportDialog({
  open,
  onOpenChange,
  onImport,
  isPending,
}: JsonImportDialogProps) {
  const [raw, setRaw] = useState("");

  function handleImport() {
    try {
      const data = JSON.parse(raw);
      if (typeof data !== "object" || data === null) {
        toast.error("JSON must be an object");
        return;
      }
      onImport(data);
    } catch {
      toast.error("Invalid JSON");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Import Profile JSON</DialogTitle>
        </DialogHeader>
        <Textarea
          rows={12}
          placeholder="Paste your master_resume.json content here..."
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          className="font-mono text-xs"
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleImport} disabled={isPending || !raw.trim()}>
            {isPending ? "Importing..." : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
