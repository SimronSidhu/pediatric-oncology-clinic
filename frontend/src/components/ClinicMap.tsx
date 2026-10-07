import type { Frame, FrameAgent } from "../types";
import { ROLE_META, ZONES } from "../types";

const HIDDEN = new Set(["offsite", "departed"]);

function slot(zoneKey: string, index: number, total: number) {
  const zone = ZONES[zoneKey] ?? ZONES.entrance;
  const cols = Math.max(2, Math.min(6, Math.ceil(Math.sqrt(Math.max(total, 1) * 1.4))));
  const col = index % cols;
  const row = Math.floor(index / cols);
  const rows = Math.ceil(total / cols);
  const x = zone.x + 12 + ((col + 0.5) / cols) * (zone.w - 16);
  const y = zone.y + 16 + ((row + 0.5) / Math.max(rows, 1)) * (zone.h - 18);
  return { x, y };
}

export function ClinicMap({
  frame,
  selected,
  onSelect,
  speed,
}: {
  frame: Frame | null;
  selected: string | null;
  onSelect: (id: string) => void;
  speed: number;
}) {
  const agents = (frame?.agents ?? []).filter((agent) => !HIDDEN.has(agent.loc) && ZONES[agent.loc]);
  const grouped = new Map<string, FrameAgent[]>();
  for (const agent of agents) {
    const list = grouped.get(agent.loc) ?? [];
    list.push(agent);
    grouped.set(agent.loc, list);
  }
  for (const list of grouped.values()) {
    list.sort((a, b) => a.id.localeCompare(b.id));
  }
  const queues = frame?.queues ?? {};
  const badges: Record<string, number> = {
    reception: queues.admin ?? 0,
    waiting_room: (queues.nurse ?? 0) + (queues.oncologist ?? 0),
    triage: queues.nurse ?? 0,
    oncology: queues.oncologist ?? 0,
    psychosocial: (queues.social_work ?? 0) + (queues.psychology ?? 0),
    child_life: queues.child_life ?? 0,
  };
  const move = Math.max(80, 420 / speed);

  return (
    <div>
      <div className="relative h-[520px] overflow-hidden rounded border border-line bg-white">
      {Object.entries(ZONES).map(([key, zone]) => (
        <div key={key} className="room" style={{ left: `${zone.x}%`, top: `${zone.y}%`, width: `${zone.w}%`, height: `${zone.h}%` }}>
          <span>{zone.label}</span>
          {badges[key] ? <em>queue {badges[key]}</em> : null}
        </div>
      ))}
      {agents.map((agent) => {
        const peers = grouped.get(agent.loc) ?? [agent];
        const point = slot(agent.loc, Math.max(0, peers.findIndex((item) => item.id === agent.id)), peers.length);
        const meta = ROLE_META[agent.role] ?? ROLE_META.patient;
        return (
          <button
            key={agent.id}
            type="button"
            className={`token ${agent.role === "caregiver" ? "caregiver" : ""}`}
            data-hot={agent.stress >= 68}
            data-selected={selected === agent.id}
            title={`${meta.label} ${agent.id}: ${agent.task}`}
            style={{
              left: `${point.x}%`,
              top: `${point.y}%`,
              background: meta.color,
              transition: `left ${move}ms ease, top ${move}ms ease`,
            }}
            onClick={() => onSelect(agent.id)}
          >
            {meta.short}
          </button>
        );
      })}
      </div>
      <div className="mt-2 flex flex-wrap gap-2 px-1 text-[11px] text-mist">
        {Object.entries(ROLE_META).map(([key, meta]) => (
          <span key={key} className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2 w-2" style={{ background: meta.color }} />
            {meta.label}
          </span>
        ))}
      </div>
    </div>
  );
}
