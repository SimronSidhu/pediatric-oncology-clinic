import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SimulationResult } from "../types";
import { pct } from "../lib/format";

const PHASE: Record<string, string> = {
  Arrival: "#8a97a6",
  "Check-in": "#5c6773",
  Nurse: "#1e4d78",
  Oncology: "#243044",
  Treatment: "#6e4a62",
  Psychosocial: "#4e5a78",
  Exit: "#3f5c4e",
};

export function Analytics({ result }: { result: SimulationResult | null }) {
  if (!result) return <p className="text-sm text-mist">Run a clinic day to open the end-of-day board.</p>;
  const { metrics, bottleneck, funnel, sankey, gantt } = result;
  const util = Object.entries(metrics.utilization).map(([name, value]) => ({
    name: name.replaceAll("_", " "),
    day: Math.round(value * 100),
    session: Math.round((metrics.session_utilization[name] ?? 0) * 100),
  }));
  const waits = histogram(metrics.waits, 8);
  const maxT = Math.max(60, ...gantt.flatMap((row) => row.segments.map((segment) => segment.end)));

  return (
    <div className="space-y-6">
      <section className="rounded border border-line border-l-4 border-l-ink bg-white px-5 py-4">
        <p className="text-xs text-mist">Primary bottleneck</p>
        <h2 className="mt-1 text-lg font-semibold">{bottleneck.label}</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6">{bottleneck.interpretation}</p>
        <p className="mt-3 text-sm text-mist">
          Day utilization {pct(bottleneck.utilization)} · in-session {pct(bottleneck.session_utilization)} · mean wait {bottleneck.mean_wait} min · peak queue {bottleneck.peak_queue}
        </p>
      </section>
      <section className="grid gap-3 md:grid-cols-4">
        <Tile label="Families with need" value={metrics.families_with_need} />
        <Tile label="Identified" value={metrics.identified} />
        <Tile label="Missed" value={metrics.missed} accent />
        <Tile label="Supported" value={metrics.supported} />
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Staff utilization">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={util}>
              <CartesianGrid stroke="#e6eaee" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="day" fill="#1e4d78" name="Day %" />
              <Bar dataKey="session" fill="#8a97a6" name="In-session %" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Wait before the oncologist">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={waits}>
              <CartesianGrid stroke="#e6eaee" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#1b2430" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </section>
      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-line bg-white p-4">
          <h3 className="text-sm font-semibold">Detection funnel</h3>
          <ol className="mt-4 space-y-2 text-sm">
            {Object.entries(funnel).map(([key, value]) => (
              <li key={key} className="flex items-center justify-between border-b border-line py-1">
                <span className="capitalize text-mist">{key.replaceAll("_", " ")}</span>
                <span className="font-medium">{value}</span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-xs text-mist">
            Screening sensitivity {pct(metrics.sensitivity)} · false-positive referrals {metrics.false_positive_referrals} ({pct(metrics.false_positive_share)}) · time above 80% occupancy {pct(metrics.above_80_share)}
          </p>
        </div>
        <div className="rounded border border-line bg-white p-4">
          <h3 className="text-sm font-semibold">Flow</h3>
          <div className="mt-4 space-y-2">
            {sankey.links.map((link) => (
              <div key={`${link.source}-${link.target}`} className="flex items-center gap-3 text-sm">
                <span className="w-28 text-mist">{sankey.nodes[link.source]?.name}</span>
                <div className="h-1 flex-1 bg-[#e6eaee]">
                  <div className="h-1 bg-teal" style={{ width: `${Math.min(100, (link.value / Math.max(1, metrics.throughput)) * 100)}%` }} />
                </div>
                <span className="w-28 text-right">{sankey.nodes[link.target]?.name}</span>
                <span className="w-6 text-right tabular-nums">{link.value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="overflow-auto rounded border border-line bg-white p-4">
        <h3 className="text-sm font-semibold">Day timeline</h3>
        <div className="mt-4 min-w-[720px] space-y-1">
          {gantt.map((row) => (
            <div key={row.id} className="grid grid-cols-[72px_1fr] items-center gap-2">
              <span className="text-xs text-mist">{row.id}</span>
              <div className="relative h-2 bg-[#eef1f4]">
                {row.segments.map((segment) => (
                  <i
                    key={`${segment.phase}-${segment.start}`}
                    className="absolute top-0 h-2"
                    style={{
                      left: `${(segment.start / maxT) * 100}%`,
                      width: `${Math.max(0.8, ((segment.end - segment.start) / maxT) * 100)}%`,
                      background: PHASE[segment.phase] ?? "#8a6a3b",
                    }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function histogram(values: number[], bins: number) {
  if (!values.length) return [];
  const max = Math.max(...values, 1);
  const width = max / bins;
  return Array.from({ length: bins }, (_, index) => {
    const start = index * width;
    const end = start + width;
    return {
      label: `${Math.round(start)}–${Math.round(end)}`,
      count: values.filter((value) => value >= start && (index === bins - 1 ? value <= end : value < end)).length,
    };
  });
}

function Tile({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className={`border bg-white p-3 ${accent ? "border-coral/40" : "border-line"}`}>
      <p className="text-xs text-mist">{label}</p>
      <p className={`text-lg font-semibold tabular-nums ${accent ? "text-coral" : "text-ink"}`}>{value}</p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded border border-line bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {children}
    </div>
  );
}
