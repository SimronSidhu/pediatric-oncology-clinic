import type { Frame, Metrics } from "../types";
import { pct } from "../lib/format";

const UTIL_LABELS: [string, string][] = [
  ["nurse", "Nursing"],
  ["oncologist", "Oncology"],
  ["social_work", "Social work"],
  ["psychology", "Psychology"],
  ["child_life", "Child life"],
  ["admin", "Reception"],
];

export function LiveMetrics({ frame, metrics }: { frame: Frame | null; metrics: Metrics | null }) {
  const live = frame?.live;
  return (
    <section className="space-y-3">
      <div className="grid grid-cols-3 gap-px border border-line bg-line">
        <Stat label="With need" value={live?.with_need ?? metrics?.families_with_need ?? "—"} hint="latent" />
        <Stat label="Identified" value={live?.identified ?? metrics?.identified ?? "—"} hint="referred" />
        <Stat label="Missed" value={live?.missed ?? metrics?.missed ?? "—"} hint="so far" accent />
      </div>
      <div className="grid grid-cols-2 gap-px border border-line bg-line">
        <Stat label="Mean wait" value={live ? `${live.mean_wait}m` : "—"} />
        <Stat label="Psych queue" value={live?.psych_queue ?? 0} />
        <Stat label="Screened" value={live?.screened ?? 0} />
        <Stat label="In clinic" value={live?.in_clinic ?? 0} />
      </div>
      <div className="rounded border border-line bg-white p-3">
        <p className="text-xs font-medium text-mist">Occupancy</p>
        <div className="mt-3 space-y-2">
          {UTIL_LABELS.map(([key, label]) => {
            const value = frame?.occupancy?.[key] ?? 0;
            return (
              <div key={key}>
                <div className="mb-1 flex justify-between text-xs text-mist">
                  <span>{label}</span>
                  <span>{pct(value)}</span>
                </div>
                <div className="h-1 bg-[#e6eaee]">
                  <div className="h-1 bg-teal" style={{ width: `${Math.min(100, value * 100)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {metrics ? (
        <p className="text-xs text-mist">
          {metrics.families_with_need} families with need by the end of this day. Counts on the floor update as people move.
        </p>
      ) : null}
    </section>
  );
}

function Stat({ label, value, hint, accent }: { label: string; value: string | number; hint?: string; accent?: boolean }) {
  return (
    <div className={`px-3 py-2 ${accent ? "bg-[#faf6f5]" : "bg-white"}`}>
      <p className="text-xs text-mist">{label}</p>
      <p className={`text-lg font-semibold tabular-nums ${accent ? "text-coral" : "text-ink"}`}>{value}</p>
      {hint ? <p className="text-[11px] text-mist">{hint}</p> : null}
    </div>
  );
}
