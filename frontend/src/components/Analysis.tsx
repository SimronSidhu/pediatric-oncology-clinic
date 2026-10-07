import { About } from "./About";
import { Agents } from "./Agents";
import { Analytics } from "./Analytics";
import { Architecture } from "./Architecture";
import { ModelLab } from "./ModelLab";
import { Research } from "./Research";
import type { Scenario, SimulationResult } from "../types";

const SECTIONS = [
  ["day", "This day"],
  ["research", "Research"],
  ["roster", "Roster"],
  ["model", "Model"],
  ["methods", "Methods"],
] as const;

export function Analysis({
  result,
  scenario,
  onApply,
}: {
  result: SimulationResult | null;
  scenario: Scenario | null;
  onApply: (patch: Partial<Scenario>) => void;
}) {
  return (
    <div className="grid items-start gap-8 lg:grid-cols-[9.5rem_minmax(0,1fr)]">
      <nav className="sticky top-4 flex gap-3 overflow-auto text-sm lg:flex-col lg:gap-1">
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="text-mist hover:text-ink">
            {label}
          </a>
        ))}
      </nav>
      <div className="min-w-0 space-y-12">
        <section id="day" className="scroll-mt-4">
          <Analytics result={result} />
        </section>
        <section id="research" className="scroll-mt-4">
          <h2 className="mb-3 text-lg font-semibold">Research</h2>
          <Research scenario={scenario} onApply={onApply} />
        </section>
        <section id="roster" className="scroll-mt-4">
          <h2 className="mb-3 text-lg font-semibold">Roster</h2>
          <Agents result={result} />
        </section>
        <section id="model" className="scroll-mt-4">
          <ModelLab />
        </section>
        <section id="methods" className="scroll-mt-4 space-y-8">
          <Architecture />
          <About />
        </section>
      </div>
    </div>
  );
}
