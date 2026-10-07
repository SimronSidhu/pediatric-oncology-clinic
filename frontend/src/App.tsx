import { useEffect, useMemo, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { AgentPanel } from "./components/AgentPanel";
import { Analysis } from "./components/Analysis";
import { ClinicMap } from "./components/ClinicMap";
import { EventStream } from "./components/EventStream";
import { Experiments } from "./components/Experiments";
import { LiveMetrics } from "./components/LiveMetrics";
import { usePlayback } from "./hooks/usePlayback";
import { clock } from "./lib/format";
import { fetchPresets, runSimulation } from "./services/api";
import type { Frame, Preset, Scenario, SimulationResult } from "./types";

const TABS = ["Clinic", "Analysis"] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Clinic");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const playback = usePlayback(result?.horizon ?? 0);

  useEffect(() => {
    fetchPresets()
      .then(async (payload) => {
        setPresets(payload.presets);
        const demo = payload.presets.find((item) => item.id === "universal") ?? payload.presets[0];
        if (!demo) throw new Error("No demo scenario is configured.");
        setScenario(demo.scenario);
        return runSimulation(demo.scenario, true);
      })
      .then((day) => {
        setResult(day);
        playback.setT(0);
      })
      .catch(() => setError("The simulation API is not responding. Start it on port 8000 and reload."));
  }, []);

  async function run(next: Scenario) {
    setScenario(next);
    setLoading(true);
    setError("");
    playback.setPlaying(false);
    try {
      const day = await runSimulation(next, true);
      setResult(day);
      playback.setT(0);
      playback.setPlaying(true);
      setTab("Clinic");
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The day could not be simulated.");
    } finally {
      setLoading(false);
    }
  }

  const frame = useMemo(() => (result ? frameAt(result.frames, playback.t) : null), [result, playback.t]);
  const agent = frame?.agents.find((item) => item.id === selected) ?? null;
  const events = (result?.events ?? []).filter((event) => event.t <= playback.t && (filter === "all" || event.category === filter));

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[15px] font-semibold text-ink">Pediatric Oncology Clinic</h1>
            <p className="text-sm text-mist">Digital twin</p>
          </div>
          <div className="flex flex-wrap items-center">
            <span className="mr-3 font-medium tabular-nums text-ink">{clock(result?.open_hour ?? 8, playback.t)}</span>
            <button type="button" className="inline-flex h-8 items-center border border-ink bg-ink px-3 text-sm text-white" onClick={() => {
              if (!result || !scenario) {
                if (scenario) void run(scenario);
                return;
              }
              if (playback.t >= result.horizon - 0.5) playback.setT(0);
              playback.setPlaying(true);
            }}>
              {loading ? "Simulating…" : "Start"}
            </button>
            <button type="button" className="inline-flex h-8 items-center border border-l-0 border-line bg-white px-3 text-sm" onClick={() => scenario && void run(scenario)}>
              Rerun
            </button>
            <button type="button" className="inline-flex h-8 items-center border border-l-0 border-line bg-white px-2" onClick={() => playback.setPlaying(!playback.playing)} aria-label={playback.playing ? "Pause" : "Play"}>
              {playback.playing ? <Pause size={15} /> : <Play size={15} />}
            </button>
            {([1, 2, 5] as const).map((value) => (
              <button key={value} type="button" className={`inline-flex h-8 items-center border border-l-0 border-line px-2.5 text-sm ${playback.speed === value ? "bg-ink text-white" : "bg-white text-ink"}`} onClick={() => playback.setSpeed(value)}>
                {value}×
              </button>
            ))}
            <button type="button" className="inline-flex h-8 items-center border border-l-0 border-line bg-white px-2" aria-label="Reset" onClick={() => { playback.setPlaying(false); playback.setT(0); }}>
              <RotateCcw size={15} />
            </button>
          </div>
        </div>
        <nav className="flex gap-5 overflow-auto px-5">
          {TABS.map((item) => (
            <button key={item} type="button" onClick={() => setTab(item)} className={`h-9 border-b-2 text-sm ${tab === item ? "border-ink font-medium text-ink" : "border-transparent text-mist"}`}>
              {item}
            </button>
          ))}
        </nav>
      </header>
      <main className="px-5 py-4">
      {tab !== "Analysis" ? <p className="mb-3 text-sm text-mist">{story(frame)}</p> : null}
      {error ? <p className="mb-3 text-sm text-coral">{error}</p> : null}
      {tab !== "Analysis" ? (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.72fr)]">
          <div className="space-y-4">
            <ClinicMap frame={frame} selected={selected} speed={playback.speed} onSelect={setSelected} />
            <EventStream events={events} filter={filter} onFilter={setFilter} />
          </div>
          <div className="space-y-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-auto lg:pr-1">
            <Experiments scenario={scenario} presets={presets} onChange={setScenario} onRun={(next) => void run(next)} />
            <LiveMetrics frame={frame} metrics={result?.metrics ?? null} />
            {result ? <AgentPanel result={result} agent={agent} t={playback.t} onClose={() => setSelected(null)} /> : null}
          </div>
        </div>
      ) : null}
      {tab === "Analysis" ? (
        <Analysis
          result={result}
          scenario={scenario}
          onApply={(patch) => {
            if (scenario) void run({ ...scenario, ...patch, name: patch.name || scenario.name });
          }}
        />
      ) : null}
      <p className="mt-8 text-xs text-mist">
        This application is a research and educational simulation using synthetic data. It is not a clinical decision-support system and should not be used to guide patient care.
      </p>
      </main>
    </div>
  );
}

function frameAt(frames: Frame[], t: number): Frame | null {
  if (!frames.length) return null;
  let chosen = frames[0];
  for (const frame of frames) {
    if (frame.t <= t + 0.001) chosen = frame;
    else break;
  }
  return chosen;
}

function story(frame: Frame | null): string {
  if (!frame) return "The demo day is universal distress screening: 20 visits, three nurses, two oncologists, and one social worker.";
  if ((frame.queues.social_work ?? 0) >= 2 || frame.live.psych_queue >= 3) {
    return "Social work is backing up. Screening is identifying need faster than one clinician can see it.";
  }
  if (frame.live.missed > 0) {
    return `${frame.live.missed} high-need ${frame.live.missed === 1 ? "family has" : "families have"} left without a psychosocial referral.`;
  }
  if (frame.live.screened >= 4 && frame.t < 150) {
    return "Check-in screening is scoring distress while the oncology rooms are still on schedule.";
  }
  if (frame.live.discharged >= frame.live.arrived && frame.live.arrived > 0) {
    return "The day is finished. Open Analysis for the end-of-day counts, or add a social worker and rerun.";
  }
    return "Families move from arrival through nursing and oncology. Psychosocial demand follows the scores.";
}
