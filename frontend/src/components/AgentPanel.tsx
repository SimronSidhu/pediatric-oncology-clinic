import type { FrameAgent, PatientRecord, SimulationResult, StaffRecord } from "../types";
import { ROLE_META } from "../types";
import { clock } from "../lib/format";

export function AgentPanel({
  result,
  agent,
  t,
  onClose,
}: {
  result: SimulationResult;
  agent: FrameAgent | null;
  t: number;
  onClose: () => void;
}) {
  if (!agent) {
    return (
      <aside className="rounded border border-dashed border-line bg-white p-4 text-sm text-mist">
        Select a person on the floor to see their task, stress, and why they are there.
      </aside>
    );
  }
  const meta = ROLE_META[agent.role] ?? { label: agent.role, short: "?", color: "#24344d" };
  const patient = result.patients.find((item) => item.id === agent.id || item.caregiver.id === agent.id) ?? null;
  const staff = result.staff.find((item) => item.id === agent.id) ?? null;
  const subject = patient && agent.role === "caregiver" ? patient.caregiver : null;
  const name = patient && agent.role === "patient" ? patient.name : subject?.name ?? staff?.name ?? agent.id;
  const goal = patient && agent.role === "patient" ? patient.goal : subject?.goal ?? staff?.goal ?? "";
  const events = result.events.filter(
    (event) => event.t <= t && (event.agent_id === agent.id || event.agent_id === patient?.id),
  );

  return (
    <aside className="rounded border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-mist">{meta.label}</p>
          <h3 className="text-base font-semibold text-ink">{name}</h3>
          <p className="text-sm text-mist">{agent.id} · {agent.state.replaceAll("_", " ").toLowerCase()}</p>
        </div>
        <button type="button" className="text-sm text-mist" onClick={onClose}>Close</button>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Fact label="Current task" value={agent.task} />
        <Fact label="Next" value={agent.next} />
        <Fact label="Location" value={agent.loc.replaceAll("_", " ")} />
        <Fact label="Goal" value={goal} />
        <Fact label="Stress" value={`${Math.round(agent.stress)} / 100`} />
        <Fact label="Workload" value={`${Math.round(agent.workload)}`} />
      </dl>
      <Meter label="Stress" value={agent.stress} />
      {patient && agent.role !== "caregiver" ? (
        <PatientFacts patient={patient} openHour={result.open_hour} revealed={events} score={agent.score} />
      ) : null}
      {subject ? (
        <p className="mt-3 text-sm text-ink">Caregiver distress {Math.round(subject.distress)}. {subject.goal}</p>
      ) : null}
      {staff ? <StaffFacts staff={staff} /> : null}
      {events.length > 0 ? (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-mist">Recent reasons</p>
          {events.slice(-4).map((event) => (
            <p key={`${event.t}-${event.type}`} className="text-sm text-ink">
              <span className="text-mist">{event.clock} </span>
              {event.reason}
            </p>
          ))}
        </div>
      ) : null}
      {patient?.memory?.length && events.some((event) => event.type === "discharged") ? (
        <p className="mt-3 text-xs text-mist">
          Memory: {patient.memory.slice(-2).map((item) => `${clock(result.open_hour, item.time)} ${item.event.replaceAll("_", " ")}`).join(" · ")}
        </p>
      ) : null}
    </aside>
  );
}

function PatientFacts({
  patient,
  openHour,
  revealed,
  score,
}: {
  patient: PatientRecord;
  openHour: number;
  revealed: { type: string; reason: string }[];
  score?: number | null;
}) {
  const referral = [...revealed].reverse().find((event) => event.type === "referral_created");
  const missed = revealed.find((event) => event.type === "need_missed");
  const done = revealed.some((event) => event.type === "discharged");
  return (
    <div className="mt-4 border border-line bg-[#f4f6f8] p-3 text-sm">
      <p>{patient.age} years · {patient.cancer_category} · {patient.treatment_phase.replaceAll("_", " ")}</p>
      <p className="mt-1 text-mist">
        Appointment {clock(openHour, patient.appointment_time)} · chart risk {Math.round(patient.predicted_risk * 100)}%
      </p>
      <p className="mt-2">
        Distress score {score ?? "—"}
        {patient.high_need ? " · latent high psychosocial need is visible in this simulation" : ""}
      </p>
      <p className="mt-1">{referral ? referral.reason : "No referral yet"}</p>
      {missed ? <p className="mt-2 text-coral">{missed.reason}</p> : null}
      {done ? (
        <p className="mt-2 text-mist">
          Waits: desk {patient.waits.admin}m · nurse {patient.waits.nurse}m · oncologist {patient.waits.oncologist}m · psychosocial {patient.waits.psychosocial}m
        </p>
      ) : null}
    </div>
  );
}

function StaffFacts({ staff }: { staff: StaffRecord }) {
  return (
    <p className="mt-3 text-sm text-mist">
      {staff.on_duty ? "On duty" : "Absent"} · {staff.patients_seen} patients seen by the end of this run · {Math.round(staff.busy_minutes)} min busy · {staff.goal}
    </p>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#f4f6f8] px-3 py-2">
      <dt className="text-xs text-mist">{label}</dt>
      <dd className="mt-1 text-ink">{value}</dd>
    </div>
  );
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-xs text-mist">
        <span>{label}</span>
        <span>{Math.round(value)}</span>
      </div>
      <div className="h-1 bg-[#e6eaee]">
        <div className="h-1 bg-coral" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}
