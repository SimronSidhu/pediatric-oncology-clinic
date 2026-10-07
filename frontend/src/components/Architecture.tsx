const LAYERS = [
  ["Synthetic patient generator", "Conditional distributions over diagnosis, symptoms, distress, travel, and caregiver stress", "NumPy"],
  ["Discrete-event simulator", "Arrivals, queues, rooms, and service times", "SimPy"],
  ["Agent state machines", "Patients, caregivers, and staff with explicit legal transitions", "Python"],
  ["Decision engines", "Rules by default. An optional LLM returns JSON that Pydantic must accept", "Pydantic"],
  ["Clinic environment", "Resources, priorities, abandonment, lateness, and staff stress", "SimPy"],
  ["Analytics", "Waits, missed need, utilization, bottlenecks", "pandas"],
  ["Monte Carlo, ML, search", "Repeated days, referral-risk models, staffing grid search", "scikit-learn"],
  ["Calibration", "Rejection ABC against published screening completion, referral, and time targets", "NumPy"],
  ["Persona audit", "Same clinical facts, language access changed, rule and optional model compared", "Pydantic"],
  ["Surrogate search", "Gaussian process expected improvement over cutoff and staffing", "scikit-learn"],
  ["Learned referrals", "Episodic Q-learning versus the fixed cutoff", "NumPy"],
  ["Interactive dashboard", "Floor, playback, experiments, and charts", "React"],
];

export function Architecture() {
  return (
    <div>
      <h2 className="text-lg font-semibold">Architecture</h2>
      <p className="mt-2 text-sm leading-6 text-mist">
        SimPy runs the clock, the queues, and staff time. A decision is requested only for screening consent, what is written on the form, and whether a nurse refers. The answer has to match a schema before it changes anything.
      </p>
      <ol className="mt-6 space-y-3">
        {LAYERS.map(([title, detail, tech], index) => (
          <li key={title} className="rounded border border-line bg-white px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <p className="font-medium text-ink">{index + 1}. {title}</p>
              <span className="text-xs text-mist">{tech}</span>
            </div>
            <p className="mt-1 text-sm text-mist">{detail}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <Note title="Same seed, same day" body="Service times are drawn once. Replay uses that draw. Monte Carlo changes the seed." />
        <Note title="Playback" body="The day is simulated first and stored as a trace. Pause and speed only move through that trace." />
      </div>
    </div>
  );
}

function Note({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border border-line bg-white p-4">
      <h3 className="font-medium">{title}</h3>
      <p className="mt-1 text-sm text-mist">{body}</p>
    </div>
  );
}
