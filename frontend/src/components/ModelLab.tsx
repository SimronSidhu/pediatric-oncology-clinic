import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchModel, trainModel, type ModelReport } from "../services/api";

export function ModelLab() {
  const [report, setReport] = useState<ModelReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(train = false) {
    setBusy(true);
    setError("");
    try {
      setReport(train ? await trainModel() : await fetchModel());
    } catch (err) {
      setError(err instanceof Error ? err.message : "The model report is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load(false);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Referral-risk model</h2>
          <p className="mt-1 max-w-2xl text-sm text-mist">
            Logistic regression and a random forest predict whether a synthetic family needs a psychosocial referral. Features are known before today's screen: age, visit type, symptoms, chart distress, caregiver stress, travel, and prior support.
          </p>
        </div>
        <button type="button" className="h-8 border border-line bg-white px-3 text-sm" onClick={() => void load(true)}>
          {busy ? "Fitting…" : "Retrain"}
        </button>
      </div>
      {error ? <p className="text-sm text-coral">{error}</p> : null}
      {report ? (
        <>
          <p className="border border-line bg-white px-4 py-3 text-sm text-mist">{report.disclaimer}</p>
          <p className="text-sm text-mist">{report.n_encounters} synthetic encounters · {Math.round(report.positive_rate * 100)}% labeled as needing referral, with a small amount of label noise. Those metrics are a holdout from the same generator.</p>
          {report.shifted ? (
            <div className="border border-line bg-white p-4 text-sm">
              <h3 className="font-semibold">Shifted cohort</h3>
              <p className="mt-1 text-mist">{report.shifted.description} {report.shifted.n_encounters} encounters, {Math.round(report.shifted.positive_rate * 100)}% labeled as needing referral.</p>
              <ul className="mt-2 space-y-1">
                {report.shifted.models.map((model) => (
                  <li key={model.name}>{model.name}: ROC-AUC {model.roc_auc}, precision {model.precision}, recall {model.recall}, F1 {model.f1}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="grid gap-4 xl:grid-cols-2">
            {report.models.map((model) => (
              <article key={model.name} className="rounded border border-line bg-white p-4">
                <h3 className="text-base font-semibold">{model.name}</h3>
                <dl className="mt-3 grid grid-cols-4 gap-2 text-center text-sm">
                  <Metric label="ROC-AUC" value={model.roc_auc} />
                  <Metric label="Precision" value={model.precision} />
                  <Metric label="Recall" value={model.recall} />
                  <Metric label="F1" value={model.f1} />
                </dl>
                <p className="mt-4 text-xs font-medium text-mist">Confusion matrix</p>
                <table className="mt-2 text-sm">
                  <tbody>
                    {model.confusion_matrix.map((row, index) => (
                      <tr key={index}>
                        {row.map((cell, cellIndex) => (
                          <td key={cellIndex} className="border border-line px-4 py-2 tabular-nums">{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-4 h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={model.feature_importance.slice(0, 8)} layout="vertical" margin={{ left: 24 }}>
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="feature" width={120} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="importance" fill="#1e4d78" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </article>
            ))}
          </div>
          <p className="text-sm text-mist">
            Selective mode screens families whose predicted risk is high. Universal screening still screens everyone. Compare those two presets on the clinic floor.
          </p>
        </>
      ) : busy ? <p className="text-sm text-mist">Fitting models on synthetic encounters…</p> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-[#f4f6f8] px-2 py-2">
      <dt className="text-xs text-mist">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value.toFixed(2)}</dd>
    </div>
  );
}
