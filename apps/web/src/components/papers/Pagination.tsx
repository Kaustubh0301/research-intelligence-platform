import { cn } from "@/lib/utils";

interface Props {
  page:         number;
  totalPages:   number;
  total:        number;
  perPage:      number;
  onPageChange: (p: number) => void;
}

function buildPageRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  if (current > 3) pages.push("…");
  const start = Math.max(2, current - 1);
  const end   = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) pages.push(i);
  if (current < total - 2) pages.push("…");
  pages.push(total);
  return pages;
}

export function Pagination({ page, totalPages, total, perPage, onPageChange }: Props) {
  const from  = Math.min((page - 1) * perPage + 1, total);
  const to    = Math.min(page * perPage, total);
  const pages = buildPageRange(page, totalPages);

  return (
    <div className="flex flex-col items-center gap-md py-xl">
      <p className="text-body-sm text-on-surface-variant">
        Showing {from.toLocaleString()}–{to.toLocaleString()} of{" "}
        {total.toLocaleString()} papers
      </p>

      <div className="flex items-center gap-sm">
        {/* Prev */}
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className="w-10 h-10 flex items-center justify-center rounded-lg border border-outline-variant text-on-surface-variant hover:border-im-primary hover:text-im-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <span className="material-symbols-outlined text-[20px]">chevron_left</span>
        </button>

        {/* Page numbers */}
        {pages.map((p, i) =>
          p === "…" ? (
            <span
              key={`ellipsis-${i}`}
              className="w-10 h-10 flex items-center justify-center text-on-surface-variant"
            >
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => p !== page && onPageChange(p)}
              aria-current={p === page ? "page" : undefined}
              className={cn(
                "w-10 h-10 flex items-center justify-center rounded-lg text-body-sm transition-colors",
                p === page
                  ? "bg-im-primary text-on-primary font-bold cursor-default"
                  : "border border-outline-variant text-on-surface-variant hover:border-im-primary hover:text-im-primary"
              )}
            >
              {p}
            </button>
          )
        )}

        {/* Next */}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
          className="w-10 h-10 flex items-center justify-center rounded-lg border border-outline-variant text-on-surface-variant hover:border-im-primary hover:text-im-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <span className="material-symbols-outlined text-[20px]">chevron_right</span>
        </button>
      </div>
    </div>
  );
}
