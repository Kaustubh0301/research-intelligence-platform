import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-4 -my-6 overflow-hidden">
      {/* Left sidebar skeleton */}
      <div className="w-60 border-r p-4 space-y-4">
        <Skeleton className="h-5 w-40" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
      {/* Main area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-4 space-y-4">
          <Skeleton className="h-20 w-3/4 ml-auto rounded-2xl" />
          <Skeleton className="h-32 w-3/4 rounded-2xl" />
        </div>
        <div className="border-t p-3">
          <Skeleton className="h-11 w-full rounded-xl" />
        </div>
      </div>
      {/* Right panel skeleton */}
      <div className="w-72 border-l p-4 space-y-3">
        <Skeleton className="h-5 w-36" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2 p-3 border rounded-lg">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-5 w-24 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
