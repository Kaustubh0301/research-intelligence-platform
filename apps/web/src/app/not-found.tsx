import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <h2 className="text-2xl font-semibold">404 — Not Found</h2>
      <p className="text-sm text-muted-foreground">
        This paper or page does not exist.
      </p>
      <Link
        href="/"
        className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
