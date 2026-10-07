export interface Scenario {
  name: string;
  seed: number;
  n_patients: number;
  n_nurses: number;
  n_oncologists: number;
  n_social_workers: number;
  n_psychologists: number;
  n_child_life: number;
  n_admin: number;
  open_hour: number;
  close_hour: number;
  appointment_spacing_min: number;
  mean_onc_visit_min: number;
  pct_new_diagnosis: number;
  distress_prevalence: number;
  high_distress_prevalence: number;
  mean_treatment_intensity: number;
  mean_complexity: number;
  language_support_rate: number;
  rural_rate: number;
  mean_caregiver_stress: number;
  screening_enabled: boolean;
  screening_location: "check_in" | "waiting_room" | "nurse" | "portal";
  screening_completion_rate: number;
  screening_duration_mean: number;
  screening_duration_sd: number;
  referral_threshold: number;
  alert_threshold: "moderate" | "high" | "severe";
  referral_mode: "automatic" | "nurse_review" | "oncologist_review" | "central_triage" | "learned";
  decline_rate: number;
  referral_uptake: number;
  predictive_mode: "off" | "selective" | "prioritize";
  nurse_absence: number;
  use_llm: boolean;
  mean_nurse_min: number;
  mean_social_work_min: number;
  mean_psychology_min: number;
  mean_child_life_min: number;
  mean_checkin_min: number;
  patience_min: number;
  late_provider_min: number;
}

export interface FrameAgent {
  id: string;
  role: string;
  loc: string;
  state: string;
  stress: number;
  workload: number;
  task: string;
  next: string;
  availability: string;
  distress?: number;
  score?: number | null;
  patient_id?: string;
}

export interface Frame {
  t: number;
  queues: Record<string, number>;
  occupancy: Record<string, number>;
  utilization: Record<string, number>;
  live: {
    arrived: number;
    discharged: number;
    in_clinic: number;
    screened: number;
    declined: number;
    referrals: number;
    with_need: number;
    identified: number;
    missed: number;
    supported: number;
    mean_wait: number;
    alerts: number;
    psych_queue: number;
  };
  agents: FrameAgent[];
}

export interface SimEvent {
  t: number;
  clock: string;
  type: string;
  category: string;
  agent_id: string | null;
  message: string;
  reason: string;
}

export interface PatientRecord {
  id: string;
  name: string;
  age: number;
  sex: string;
  visit_type: string;
  cancer_category: string;
  treatment_phase: string;
  treatment_intensity: number;
  symptom_burden: number;
  baseline_distress: number;
  psychosocial_need: number;
  high_need: boolean;
  travel_category: string;
  language_support: boolean;
  appointment_time: number;
  arrival_time: number;
  discharge_time: number | null;
  urgent: boolean;
  predicted_risk: number;
  goal: string;
  screen_score: number | null;
  screen_category: string;
  screen_completed: boolean;
  screen_declined: boolean;
  identified: boolean;
  identification_route: string;
  referral_target: string;
  referral_reason: string;
  referral_completed: boolean;
  left_before_psych: boolean;
  missed: boolean;
  missed_reason: string;
  received_support: boolean;
  waits: { admin: number; nurse: number; oncologist: number; psychosocial: number };
  cycle_time: number;
  interactions: { time: number; with: string; kind: string }[];
  memory: { time: number; event: string; [key: string]: string | number }[];
  caregiver: {
    id: string;
    name: string;
    relationship: string;
    stress: number;
    distress: number;
    goal: string;
    memory: { time: number; event: string }[];
  };
}

export interface StaffRecord {
  id: string;
  name: string;
  role: string;
  goal: string;
  on_duty: boolean;
  patients_seen: number;
  busy_minutes: number;
  overtime_minutes: number;
  stress: number;
  final_task: string;
  final_state: string;
}

export interface Metrics {
  families_with_need: number;
  identified: number;
  missed: number;
  detected: number;
  supported: number;
  unserved: number;
  screened: number;
  declined: number;
  incomplete: number;
  referrals: number;
  referrals_completed: number;
  left_before_psych: number;
  false_positive_referrals: number;
  false_positive_share: number;
  sensitivity: number;
  detection_rate: number;
  missed_rate: number;
  support_rate: number;
  mean_wait: number;
  median_wait: number;
  max_wait: number;
  mean_psych_wait: number;
  max_psych_wait: number;
  mean_cycle: number;
  throughput: number;
  alerts: number;
  overtime: number;
  mean_staff_stress: number;
  max_staff_stress: number;
  max_queue: Record<string, number>;
  utilization: Record<string, number>;
  session_utilization: Record<string, number>;
  mean_role_wait: Record<string, number>;
  above_80_share: number;
  clinic_duration: number;
  waits: number[];
  psych_waits: number[];
}

export interface SimulationResult {
  scenario: Scenario;
  seed: number;
  horizon: number;
  open_hour: number;
  frames: Frame[];
  events: SimEvent[];
  metrics: Metrics;
  bottleneck: {
    role: string;
    label: string;
    utilization: number;
    session_utilization: number;
    mean_wait: number;
    peak_queue: number;
    interpretation: string;
  };
  funnel: Record<string, number>;
  sankey: { nodes: { name: string }[]; links: { source: number; target: number; value: number }[] };
  patients: PatientRecord[];
  staff: StaffRecord[];
  gantt: { id: string; name: string; segments: { phase: string; start: number; end: number }[] }[];
}

export interface Preset {
  id: string;
  description: string;
  scenario: Scenario;
}

export const ROLE_META: Record<string, { label: string; short: string; color: string }> = {
  patient: { label: "Patient", short: "P", color: "#8c3a32" },
  caregiver: { label: "Caregiver", short: "C", color: "#8a6230" },
  nurse: { label: "Nurse", short: "N", color: "#1e4d78" },
  oncologist: { label: "Oncologist", short: "O", color: "#243044" },
  social_worker: { label: "Social worker", short: "SW", color: "#4e5a78" },
  psychologist: { label: "Psychologist", short: "Ps", color: "#3d6278" },
  child_life: { label: "Child life", short: "CL", color: "#6e4a62" },
  admin: { label: "Admin", short: "Ad", color: "#3f5c4e" },
  coordinator: { label: "Coordinator", short: "Co", color: "#5c5346" },
};

export const ZONES: Record<string, { x: number; y: number; w: number; h: number; label: string }> = {
  entrance: { x: 2.5, y: 4, w: 16, h: 18, label: "Arrival" },
  reception: { x: 2.5, y: 24, w: 16, h: 24, label: "Reception" },
  waiting_room: { x: 20.5, y: 4, w: 46, h: 40, label: "Waiting room" },
  triage: { x: 68.5, y: 4, w: 29, h: 22, label: "Triage" },
  staff: { x: 2.5, y: 50, w: 16, h: 22, label: "Staff workroom" },
  oncology: { x: 68.5, y: 28, w: 29, h: 26, label: "Oncology rooms" },
  child_life: { x: 2.5, y: 74, w: 16, h: 22, label: "Child life" },
  psychosocial: { x: 20.5, y: 52, w: 46, h: 32, label: "Psychosocial" },
  treatment: { x: 68.5, y: 56, w: 29, h: 28, label: "Treatment" },
  exit: { x: 20.5, y: 86, w: 20, h: 10, label: "Exit" },
};
