import { useEffect, useRef } from "react";
import type { SimEvent } from "../types";

const FILTERS = ["all", "patient", "clinical", "psychosocial", "alert", "delay", "staff", "system"] as const;

export function EventStream({
  events,
  filter,
  onFilter,
}: {
  events: SimEvent[];
  filter: string;
  onFilter: (value: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events.length]);
  return (
    <section className="rounded border border-line bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-3 py-2">
        <p className="text-xs font-medium text-mist">Event log</p>
        {FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onFilter(item)}
            className={`text-xs capitalize ${filter === item ? "font-medium text-ink" : "text-mist"}`}
          >
            {item}
          </button>
        ))}
      </div>
      <div ref={ref} className="h-40 space-y-1 overflow-auto px-4 py-3 font-mono text-[12px] leading-5">
        {events.length === 0 ? <p className="text-mist">Events appear as the clinic day advances.</p> : null}
        {events.map((event, index) => (
          <p key={`${event.t}-${event.type}-${index}`}>
            <span className="text-teal">{event.message}</span>
            <span className="text-mist"> — {event.reason}</span>
          </p>
        ))}
      </div>
    </section>
  );
}
