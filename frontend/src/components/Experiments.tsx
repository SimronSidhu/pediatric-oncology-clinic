import { useState } from "react";
import type { Scenario } from "../types";
import { compareScenarios, runMonteCarlo, runOptimization, type OptimizationReport } from "../services/api";

type CompareRow = Awaited<ReturnType<typeof compareScenarios>>["results"][number];
type Monte = Awaited<ReturnType<typeof runMonteCarlo>>;

export function Experiments({
  scenario,
  onChange,
  onRun,
  presets,
}: {
  scenario: Scenario | null;
  onChange: (scenario: Scenario) => void;
  onRun: (scenario: Scenario) => void;
  presets: { id: string; description: string; scenario: Scenario }[];
}) {
  const [compare, setCompare] = useState<CompareRow[] | null>(null);
  const [monte, setMonte] = useState<Monte | null>(null);
  const [runs, setRuns] = useState(30);
  const [plan, setPlan] = useState<OptimizationReport | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function act(label: string, work: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await work();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The experiment failed.");
    } finally {
      setBusy("");
    }
  }

  if (!scenario) return <p className="text-sm text-mist">Loading the demo scenario…</p>;

  const trio: Scenario[] = [
    { ...scenario, name: "Baseline", screening_enabled: false, predictive_mode: "off" },
    { ...scenario, name: "Universal screening", screening_enabled: true, predictive_mode: "off", screening_location: "check_in", referral_mode: "automatic" },
    { ...scenario, name: "Screening + extra social worker", screening_enabled: true, predictive_mode: "off", n_social_workers: scenario.n_social_workers + 1 },
  ];

  return (
    <div className="space-y-6">
      <section id="presets">
        <h2 className="text-sm font-semibold">Presets</h2>
        <p className="mt-1 text-sm text-mist">Rerun this seeded day with a different workflow.</p>
        <div className="mt-3 space-y-2">
          {presets.map((item) => {
            const active = item.scenario.name === scenario.name;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onRun(item.scenario)}
                className={`w-full border bg-white p-2.5 text-left ${active ? "border-ink" : "border-line hover:border-ink"}`}
              >
                <p className="text-sm font-medium text-ink">{item.scenario.name}</p>
                <p className="mt-0.5 text-xs text-mist">{item.description}</p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="border border-line bg-white p-4">
        <h3 className="text-sm font-semibold">Adjust this day</h3>
        <div className="mt-4 grid gap-4">
          <NumberField label="Patients" value={scenario.n_patients} min={8} max={40} onChange={(value) => onChange({ ...scenario, n_patients: value })} />
          <NumberField label="Nurses" value={scenario.n_nurses} min={1} max={6} onChange={(value) => onChange({ ...scenario, n_nurses: value })} />
          <NumberField label="Oncologists" value={scenario.n_oncologists} min={1} max={4} onChange={(value) => onChange({ ...scenario, n_oncologists: value })} />
          <NumberField label="Social workers" value={scenario.n_social_workers} min={0} max={4} onChange={(value) => onChange({ ...scenario, n_social_workers: value })} />
          <NumberField label="Psychologists" value={scenario.n_psychologists} min={0} max={3} onChange={(value) => onChange({ ...scenario, n_psychologists: value })} />
          <NumberField label="Child life" value={scenario.n_child_life} min={0} max={3} onChange={(value) => onChange({ ...scenario, n_child_life: value })} />
          <NumberField label="Spacing (min)" value={scenario.appointment_spacing_min} min={10} max={45} onChange={(value) => onChange({ ...scenario, appointment_spacing_min: value })} />
          <NumberField label="Mean oncology visit" value={scenario.mean_onc_visit_min} min={12} max={40} onChange={(value) => onChange({ ...scenario, mean_onc_visit_min: value })} />
          <NumberField label="Clinic close" value={scenario.close_hour} min={14} max={19} onChange={(value) => onChange({ ...scenario, close_hour: value })} />
          <ShareField label="New diagnosis" value={scenario.pct_new_diagnosis} onChange={(value) => onChange({ ...scenario, pct_new_diagnosis: value })} />
          <ShareField label="Distress prevalence" value={scenario.distress_prevalence} onChange={(value) => onChange({ ...scenario, distress_prevalence: value })} />
          <ShareField label="High distress" value={scenario.high_distress_prevalence} onChange={(value) => onChange({ ...scenario, high_distress_prevalence: value })} />
          <ShareField label="Language support" value={scenario.language_support_rate} onChange={(value) => onChange({ ...scenario, language_support_rate: value })} />
          <ShareField label="Long-distance travel" value={scenario.rural_rate} onChange={(value) => onChange({ ...scenario, rural_rate: value })} />
          <NumberField label="Referral threshold" value={scenario.referral_threshold} min={0} max={10} onChange={(value) => onChange({ ...scenario, referral_threshold: value })} />
          <ShareField label="Decline rate" value={scenario.decline_rate} onChange={(value) => onChange({ ...scenario, decline_rate: value })} />
          <ShareField label="Screen completion" value={scenario.screening_completion_rate} onChange={(value) => onChange({ ...scenario, screening_completion_rate: value })} />
          <NumberField label="Nurses absent" value={scenario.nurse_absence} min={0} max={2} onChange={(value) => onChange({ ...scenario, nurse_absence: value })} />
        </div>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={scenario.screening_enabled} onChange={(event) => onChange({ ...scenario, screening_enabled: event.target.checked })} />
            Distress screening
          </label>
          <Select label="Where" value={scenario.screening_location} options={["check_in", "waiting_room", "nurse", "portal"]} onChange={(value) => onChange({ ...scenario, screening_location: value as Scenario["screening_location"] })} />
          <Select label="Routing" value={scenario.referral_mode} options={["automatic", "nurse_review", "oncologist_review", "central_triage", "learned"]} onChange={(value) => onChange({ ...scenario, referral_mode: value as Scenario["referral_mode"] })} />
          <Select label="Alert" value={scenario.alert_threshold} options={["moderate", "high", "severe"]} onChange={(value) => onChange({ ...scenario, alert_threshold: value as Scenario["alert_threshold"] })} />
          <Select label="Predictive" value={scenario.predictive_mode} options={["off", "selective", "prioritize"]} onChange={(value) => onChange({ ...scenario, predictive_mode: value as Scenario["predictive_mode"] })} />
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={scenario.use_llm} onChange={(event) => onChange({ ...scenario, use_llm: event.target.checked })} />
            Model decisions
          </label>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-mist">
          Model decisions use the API key for screening consent, disclosure, and nurse review. The clock and the queues stay in the simulator. Comparison, Monte Carlo, and staffing search use the rules.
        </p>
        <button type="button" className="mt-4 h-8 bg-ink px-3 text-sm text-white" onClick={() => onRun({ ...scenario, name: scenario.name || "Custom day" })}>
          Run this day
        </button>
      </section>

      <section id="compare" className="scroll-mt-4 rounded border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">Comparison</h3>
            <p className="text-sm text-mist">Baseline, universal screening, and screening with one more social worker. Same seed, same families.</p>
          </div>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("compare", async () => setCompare((await compareScenarios(trio)).results))}>
            {busy === "compare" ? "Running…" : "Compare scenarios"}
          </button>
        </div>
        {compare ? <CompareTable rows={compare} /> : null}
      </section>

      <section id="monte" className="scroll-mt-4 rounded border border-line bg-white p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">Monte Carlo</h3>
            <p className="text-sm text-mist">Repeat the current scenario across seeds. Summaries use the mean, median, standard deviation, and a 95% confidence interval.</p>
          </div>
          <label className="text-sm text-mist">
            Days
            <select className="ml-2 rounded-lg border border-line bg-white px-2 py-1" value={runs} onChange={(event) => setRuns(Number(event.target.value))}>
              {[10, 30, 50, 100].map((count) => <option key={count} value={count}>{count}</option>)}
            </select>
          </label>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("monte", async () => setMonte(await runMonteCarlo(scenario, runs)))}>
            {busy === "monte" ? "Running…" : "Run experiment"}
          </button>
        </div>
        {monte ? <MonteTable report={monte} /> : null}
      </section>

      <section id="staffing" className="scroll-mt-4 rounded border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold">Staffing search</h3>
            <p className="max-w-2xl text-sm text-mist">Smallest mix of nurses, social workers, and psychologists that keeps waits under 30 minutes, unsupported high-need families low, and utilization under 90%.</p>
          </div>
          <button type="button" className="h-8 bg-ink px-3 text-sm text-white" onClick={() => act("opt", async () => setPlan(await runOptimization(scenario)))}>
            {busy === "opt" ? "Searching…" : "Find a staffing plan"}
          </button>
        </div>
        {plan ? (
          <div className="mt-4 text-sm">
            <p className="text-mist">{plan.note}</p>
            <p className="mt-3">Current: {plan.current.nurses} nurses, {plan.current.social_workers} social workers, {plan.current.psychologists} psychologists.</p>
            <p className="mt-1 font-medium">Recommended: {plan.recommended.nurses} nurses, {plan.recommended.social_workers} social workers, {plan.recommended.psychologists} psychologists.</p>
            <p className="mt-1 text-mist">Mean wait {plan.recommended.mean_wait} min · social work utilization {Math.round(plan.recommended.sw_utilization * 100)}% · mean missed {plan.recommended.missed}</p>
            {plan.recommended.problems.length ? <p className="mt-2 text-coral">{plan.recommended.problems.join(" ")}</p> : null}
            <p className="mt-3 text-xs text-mist">{plan.disclaimer}</p>
          </div>
        ) : null}
      </section>
      {error ? <p className="text-sm text-coral">{error}</p> : null}
    </div>
  );
}

function CompareTable({ rows }: { rows: CompareRow[] }) {
  const metrics: [string, (row: CompareRow) => string][] = [
    ["Needs detected", (row) => pct(row.metrics.detection_rate)],
    ["Missed families", (row) => String(row.metrics.missed)],
    ["Supported", (row) => String(row.metrics.supported)],
    ["Mean wait", (row) => `${row.metrics.mean_wait} min`],
    ["Psychosocial wait", (row) => `${row.metrics.mean_psych_wait} min`],
    ["Social work utilization", (row) => pct(row.metrics.utilization.social_work ?? 0)],
    ["Referrals", (row) => String(row.metrics.referrals)],
    ["Left before assessment", (row) => String(row.metrics.left_before_psych)],
  ];
  return (
    <div className="mt-4 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-mist">
            <th className="py-2 pr-4 font-medium">Metric</th>
            {rows.map((row) => <th key={row.name} className="py-2 pr-4 font-medium">{row.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {metrics.map(([label, read]) => (
            <tr key={label} className="border-t border-line">
              <td className="py-2 pr-4">{label}</td>
              {rows.map((row) => <td key={row.name} className="py-2 pr-4 tabular-nums">{read(row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 space-y-2 text-sm text-mist">
        {rows.map((row) => <p key={row.name}><span className="text-ink">{row.bottleneck.label}.</span> {row.bottleneck.interpretation}</p>)}
      </div>
    </div>
  );
}

function MonteTable({ report }: { report: Monte }) {
  const keys = ["mean_wait", "missed", "identified", "mean_psych_wait", "detection_rate", "sw_utilization", "left_before_psych"];
  return (
    <table className="mt-4 w-full text-left text-sm">
      <thead>
        <tr className="text-mist">
          <th className="py-2">Metric</th><th>Mean</th><th>Median</th><th>SD</th><th>95% CI</th>
        </tr>
      </thead>
      <tbody>
        {keys.map((key) => {
          const row = report.summary[key];
          if (!row) return null;
          return (
            <tr key={key} className="border-t border-line">
              <td className="py-2">{key.replaceAll("_", " ")}</td>
              <td>{row.mean}</td>
              <td>{row.median}</td>
              <td>{row.std}</td>
              <td>{row.ci95[0]} – {row.ci95[1]}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="text-sm text-mist">
      {label}: <span className="text-ink">{value}</span>
      <input className="mt-1 w-full" type="range" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function ShareField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <NumberField label={label} value={Math.round(value * 100)} min={0} max={100} onChange={(next) => onChange(next / 100)} />;
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="text-mist">
      {label}
      <select className="ml-2 rounded-lg border border-line bg-white px-2 py-1 text-ink" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}
      </select>
    </label>
  );
}

