"use client";

import { Button } from "@/components/ui/Button";
import type { PaginatedMeta } from "@/lib/types";

interface PaginationProps {
  meta: PaginatedMeta;
  onPageChange: (page: number) => void;
  loading?: boolean;
}

export function Pagination({ meta, onPageChange, loading = false }: PaginationProps) {
  const { page, total_pages, total } = meta;

  if (total_pages <= 1) return null;

  return (
    <div className="flex items-center justify-between pt-6">
      <p className="text-xs text-gray-400">
        {total} knowledge base{total === 1 ? "" : "s"}
      </p>
      <div className="flex gap-1.5">
        <Button
          variant="secondary"
          disabled={page <= 1 || loading}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          disabled={page >= total_pages || loading}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
