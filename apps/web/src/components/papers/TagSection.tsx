interface Props {
  title: string;
  tags: string[];
}

export function TagSection({ title, tags }: Props) {
  if (!tags.length) return null;
  return (
    <section className="rounded-xl border bg-card p-5">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        {title}
      </h2>
      <div className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground"
          >
            {tag}
          </span>
        ))}
      </div>
    </section>
  );
}
