import { useUnfinishedOnly } from "@/useUnfinishedOnly";
import { cn } from "@/lib/utils";

/** A persistent "Show only unfinished" switch shared between Home and Feature pages. */
export function UnfinishedToggle({ className }: { className?: string }) {
  const [on, setOn] = useUnfinishedOnly();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => setOn(!on)}
      className={cn(
        "inline-flex items-center gap-2 eyebrow border hairline px-3 py-1.5 transition-colors",
        on
          ? "bg-foreground text-background border-foreground"
          : "bg-background text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn("h-2 w-2 rounded-full transition-colors", on ? "bg-background" : "bg-rule")}
      />
      Show only unfinished
    </button>
  );
}
