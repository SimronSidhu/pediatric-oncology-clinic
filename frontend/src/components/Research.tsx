import { useState } from "react";
import type { Scenario } from "../types";
import {
  runCalibration,
  runDistressFit,
  runManager,
  runPersonaAudit,
  runSurrogate,
  type CalibrationReport,
  type DistressFit,
  type ManagerReport,
  type PersonaAudit,
  type SurrogateReport,
} from "../services/api";

export function Research({
  scenario,
  onApply,
}: {
  scenario: Scenario | null;
  onApply: (patch: Partial<Scenario>) => void;
}) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [fit, setFit] = useState<CalibrationReport | null>(null);
  const [distress, setDistress] = useState<DistressFit | null>(null);
  const [personas, setPersonas] = useState<PersonaAudit | null>(null);
  const [surrogate, setSurrogate] = useState<SurrogateReport | null>(null);
  const [manager, setManager] = useState<ManagerReport | null>(null);

  async function act(label: string, work: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await work();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The research run failed.");
    } finally {
      setBusy("");
    }
  }

  if (!scenario) return <p className="text-sm text-mist">Load a clinic day before running these checks.</p>;

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-mist">
        Calibration, the score check, policy search, and the learned policy use the rules. The persona check can call the model.
      </p>
      {error ? <p className="text-sm text-coral">{error}</p> : null}

      <section className="border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Calibration</h3>
            <p className="text-sm text-mist">Rejection ABC. Eighty prior draws, each the mean of three clinic days, fit to published completion, referral, and screen time.</p>
          </div>
          <button type="button" className="h-8 bg-ink px-3 text-sm text-white" onClick={() => act("calibrate", async () => setFit(await runCalibration(scenario)))}>
            {busy === "calibrate" ? "Fitting…" : "Fit parameters"}
          </button>
        </div>
        {fit ? (
          <div className="mt-4 text-sm">
            <p className="text-mist">{fit.method}</p>
            <p className="mt-2">Closest distance {fit.best_distance} over {fit.draws} draws × {fit.replicates} days. Completion {fit.best_summary.completion}, referral if high {fit.best_summary.referral_if_high}, screen minutes {fit.best_summary.screen_minutes}.</p>
            <ul className="mt-3 space-y-2">
              {fit.targets.map((target) => (
                <li key={target.id}>
                  <span className="font-medium">{target.label}: {target.value}.</span> {target.source}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-mist">{fit.penetration_note}</p>
            <p className="mt-2 text-xs text-mist">{fit.disclaimer}</p>
            <button
              type="button"
              className="mt-3 h-8 border border-line bg-white px-3 text-sm"
              onClick={() => onApply({
                name: "Calibrated day",
                decline_rate: fit.suggested.decline_rate,
                screening_completion_rate: fit.suggested.screening_completion_rate,
                referral_uptake: fit.suggested.referral_uptake,
                screening_duration_mean: fit.suggested.screening_duration_mean,
              })}
            >
              Run the clinic with these parameters
            </button>
          </div>
        ) : null}
      </section>

      <section className="border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Score distribution</h3>
            <p className="text-sm text-mist">Full 0–10 histogram against a published mean, SD, and the shares at 4 and at 8.</p>
          </div>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("distress", async () => setDistress(await runDistressFit(scenario)))}>
            {busy === "distress" ? "Checking…" : "Compare scores"}
          </button>
        </div>
        {distress ? (
          <div className="mt-3 text-sm">
            <p>
              {distress.n_completed} completed screens. Mean {distress.mean_score} (SD {distress.sd_score}) against {distress.reference_mean} (SD {distress.reference_sd}). Share ≥ 4 is {distress.share_at_least_4} against {distress.benchmark_at_least_4}. Share ≥ 8 is {distress.share_at_least_8} against {distress.benchmark_at_least_8}. Total variation {distress.total_variation}. Kolmogorov–Smirnov {distress.ks_statistic}.
            </p>
            <table className="mt-3 w-full text-left">
              <thead>
                <tr className="text-mist">
                  <th className="py-1 pr-3 font-medium">Score</th>
                  <th className="py-1 pr-3 font-medium">This day</th>
                  <th className="py-1 font-medium">Reference</th>
                </tr>
              </thead>
              <tbody>
                {distress.bins.map((bin) => (
                  <tr key={bin.score} className="border-t border-line">
                    <td className="py-1 pr-3 tabular-nums">{bin.score}</td>
                    <td className="py-1 pr-3 tabular-nums">{bin.observed}</td>
                    <td className="py-1 tabular-nums">{bin.reference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-mist">{distress.mean_source} {distress.tail_source}</p>
            <p className="mt-2 text-mist">{distress.note}</p>
          </div>
        ) : null}
      </section>

      <section className="border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Persona audit</h3>
            <p className="text-sm text-mist">Eight matched pairs. The rule ignores language. The model is asked the same question with and without a Punjabi interpreter.</p>
          </div>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("personas", async () => setPersonas(await runPersonaAudit()))}>
            {busy === "personas" ? "Checking…" : "Audit decisions"}
          </button>
        </div>
        {personas ? (
          <div className="mt-4 text-sm">
            <p className="text-mist">{personas.design}</p>
            <p className="mt-2">
              Rules differ across language: {personas.rule_outcomes_differ ? "yes" : "no"}.
              {personas.model_outcomes_differ === null
                ? " Model calls were not returned."
                : ` Model answers differ: ${personas.model_outcomes_differ ? "yes" : "no"}. Accept rate ${personas.english_accept_rate} without an interpreter and ${personas.punjabi_accept_rate} with one. Gap ${personas.model_screening_gap}.`}
            </p>
            <table className="mt-3 w-full text-left">
              <thead>
                <tr className="text-mist">
                  <th className="py-1 pr-3 font-medium">Pair</th>
                  <th className="py-1 pr-3 font-medium">Score</th>
                  <th className="py-1 pr-3 font-medium">Rule</th>
                  <th className="py-1 font-medium">Model, English / Punjabi</th>
                </tr>
              </thead>
              <tbody>
                {personas.rows.map((row) => (
                  <tr key={row.id} className="border-t border-line">
                    <td className="py-2 pr-3">{row.id}</td>
                    <td className="py-2 pr-3">{row.score}</td>
                    <td className="py-2 pr-3">{row.english_rules.screening}, {row.english_rules.disclosure}, {row.english_rules.nurse}</td>
                    <td className="py-2">
                      {row.english_model && row.punjabi_model
                        ? `${row.english_model.screening}/${row.punjabi_model.screening}, ${row.english_model.disclosure}/${row.punjabi_model.disclosure}, ${row.english_model.nurse}/${row.punjabi_model.nurse}`
                        : "Rules only"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-mist">{personas.reading}</p>
          </div>
        ) : null}
      </section>

      <section className="border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Policy search</h3>
            <p className="text-sm text-mist">A Gaussian process searches a few hundred screening, cutoff, and staffing policies. Each score is the mean of two seeded days.</p>
          </div>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("surrogate", async () => setSurrogate(await runSurrogate(scenario)))}>
            {busy === "surrogate" ? "Searching…" : "Search policies"}
          </button>
        </div>
        {surrogate ? (
          <div className="mt-3 text-sm">
            <p>{surrogate.objective}</p>
            <p className="mt-2 font-medium">
              Best of {surrogate.evaluations} simulated policies from {surrogate.candidates} candidates: {surrogate.best.screening_enabled ? "screening on" : "screening off"}, cutoff {surrogate.best.referral_threshold}, {surrogate.best.n_social_workers} social workers, {surrogate.best.n_nurses} nurses. Utility {surrogate.best.utility}.
            </p>
            <p className="mt-2 text-xs text-mist">{surrogate.disclaimer}</p>
            <button
              type="button"
              className="mt-3 h-8 border border-line bg-white px-3 text-sm"
              onClick={() =>
                onApply({
                  name: "Searched policy",
                  screening_enabled: surrogate.best.screening_enabled,
                  referral_threshold: surrogate.best.referral_threshold,
                  n_social_workers: surrogate.best.n_social_workers,
                  n_nurses: surrogate.best.n_nurses,
                  referral_mode: "automatic",
                })
              }
            >
              Run this policy on the floor
            </button>
          </div>
        ) : null}
      </section>

      <section className="border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Learned referral policy</h3>
            <p className="text-sm text-mist">Forty-eight days of Q-learning. Each family’s outcome updates that referral. Held-out seeds are compared with the fixed cutoff.</p>
          </div>
          <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => act("manager", async () => setManager(await runManager(scenario)))}>
            {busy === "manager" ? "Training…" : "Train and compare"}
          </button>
        </div>
        {manager ? (
          <div className="mt-3 text-sm">
            <p>Learned utility {manager.evaluation.learned_utility}. Fixed cutoff {manager.evaluation.threshold_utility}. The learned policy was ahead on {manager.evaluation.learned_wins} of {manager.evaluation.runs} held-out days.</p>
            <p className="mt-2 text-mist">Returns while training: {manager.learning_curve.join(", ")}</p>
            <p className="mt-2 text-xs text-mist">{manager.disclaimer}</p>
            <button
              type="button"
              className="mt-3 h-8 border border-line bg-white px-3 text-sm"
              onClick={() => onApply({ name: "Learned referrals", referral_mode: "learned", screening_enabled: true })}
            >
              Play the day with this policy
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
