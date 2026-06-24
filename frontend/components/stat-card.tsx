import { cn } from "@/lib/utils";
import { CountUp } from "./motion/count-up";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

/** Metric tile with a mono, tabular count-up number. Values must come from real data. */
export function StatCard({
  label,
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  accent = false,
  hint,
}: {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  accent?: boolean;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "tabular text-3xl font-semibold tracking-tight",
            accent && "text-verified",
          )}
        >
          <CountUp value={value} decimals={decimals} prefix={prefix} suffix={suffix} />
        </div>
        {hint && <p className="mt-1 text-sm text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}
