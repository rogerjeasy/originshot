import { cn } from "@/lib/utils";

/**
 * The registration strip — the app's one signature device.
 *
 * Printers align colour separations against registration marks; if the marks
 * line up, the plates are true. That is this product's whole claim, so the
 * marker earns its place by carrying state rather than decorating an edge.
 *
 * The colour axis is the same one the rest of the system uses and no wider:
 * tungsten (3200K) is the light you act under, daylight (5600K) is the light
 * you inspect under. So a strip is amber while work is happening and cyan once
 * the result has been checked. There is deliberately no third accent.
 *
 * These are FILL colours. Never pair a strip with type in the same token —
 * --tungsten measures 2.00:1 on paper. Type uses .t-accent / .t-verify.
 */
export type RegistrationState = "idle" | "working" | "verified" | "attention";

const STATE_FILL: Record<RegistrationState, string> = {
  idle: "bg-border",
  working: "bg-accent",
  verified: "bg-[var(--daylight)]",
  attention: "bg-warning",
};

export function RegistrationStrip({
  state = "idle",
  orientation = "vertical",
  className,
}: {
  state?: RegistrationState;
  orientation?: "vertical" | "horizontal";
  className?: string;
}) {
  const vertical = orientation === "vertical";

  return (
    <span
      aria-hidden
      className={cn(
        "relative shrink-0 overflow-hidden rounded-full",
        vertical ? "w-[3px] self-stretch" : "h-[3px] w-full",
        STATE_FILL[state],
        className,
      )}
    >
      {/*
        Only the working state animates. A travelling highlight reads as an
        exposure sweeping the strip — the same gesture as .developing, which is
        already what this app's loading placeholders do, so the two agree.
        Suppressed entirely under reduced-motion rather than merely slowed.
      */}
      {state === "working" && (
        <span
          className={cn(
            "absolute inset-0 motion-reduce:hidden",
            "from-transparent via-white/70 to-transparent",
            vertical
              ? "animate-[registration-v_1.8s_linear_infinite] bg-gradient-to-b"
              : "animate-[registration-h_1.8s_linear_infinite] bg-gradient-to-r",
          )}
        />
      )}
    </span>
  );
}

/**
 * A strip paired with its reading. Used where the state needs a name as well as
 * a colour — colour alone is never the only channel carrying meaning.
 */
export function RegistrationLabel({
  state = "idle",
  children,
  className,
}: {
  state?: RegistrationState;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <RegistrationStrip state={state} orientation="horizontal" className="w-4" />
      <span
        className={cn(
          "label",
          state === "working" && "t-accent",
          state === "verified" && "t-verify",
          state === "attention" && "text-warning",
          state === "idle" && "text-muted-foreground",
        )}
      >
        {children}
      </span>
    </span>
  );
}
