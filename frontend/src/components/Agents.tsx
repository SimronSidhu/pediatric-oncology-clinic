import type { SimulationResult } from "../types";
import { ROLE_META } from "../types";

export function Agents({ result }: { result: SimulationResult | null }) {
  if (!result) return <p className="text-sm text-mist">The roster appears after a day is simulated.</p>;
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-semibold">Families</h3>
        <div className="mt-3 overflow-auto rounded border border-line bg-white">
          <table className="w-full min-w-[880px] text-left text-sm">
            <thead className="text-mist">
              <tr>
                {["ID", "Name", "Visit", "Distress", "Score", "Need", "Route", "Outcome"].map((heading) => (
                  <th key={heading} className="px-3 py-3 font-medium">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.patients.map((patient) => (
                <tr key={patient.id} className="border-t border-line">
                  <td className="px-3 py-2">{patient.id}</td>
                  <td className="px-3 py-2">{patient.name}</td>
                  <td className="px-3 py-2">{patient.visit_type.replaceAll("_", " ")}</td>
                  <td className="px-3 py-2">{patient.baseline_distress.toFixed(1)}</td>
                  <td className="px-3 py-2">{patient.screen_score ?? "—"}</td>
                  <td className="px-3 py-2">{patient.high_need ? "High" : "Lower"}</td>
                  <td className="px-3 py-2">{patient.identification_route.replaceAll("_", " ") || "—"}</td>
                  <td className="px-3 py-2">
                    {patient.missed ? "Missed" : patient.received_support ? "Supported" : patient.referral_target ? "Referred" : "No referral"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3 className="text-sm font-semibold">Staff</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {result.staff.map((person) => {
            const meta = ROLE_META[person.role];
            return (
              <article key={person.id} className="rounded border border-line bg-white p-3">
                <p className="text-xs text-mist">{meta?.label}</p>
                <h3 className="text-sm font-semibold">{person.name}</h3>
                <p className="text-sm text-mist">{person.goal}</p>
                <p className="mt-2 text-sm">{person.on_duty ? `${person.patients_seen} seen · ${Math.round(person.busy_minutes)} min on task` : "Absent today"}</p>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
