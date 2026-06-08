import { Skeleton } from "@/components/ui/skeleton";

export default function GraphLoading() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-4 -my-6 overflow-hidden">
      <div className="w-72 border-r bg-background">
        <div className="p-4 space-y-4">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
      <Skeleton className="flex-1 rounded-none" />
    </div>
  );
}
