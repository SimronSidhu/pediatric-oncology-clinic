import type { Preset, Scenario, SimulationResult } from "../types";

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function runSimulation(scenario: Scenario, trace = true): Promise<SimulationResult> {
  return post("/api/simulation/run", { scenario, trace });
}

export function fetchPresets(): Promise<{ presets: Preset[] }> {
  return fetch("/api/presets").then((response) => {
    if (!response.ok) throw new Error("Could not load presets");
    return response.json();
  });
}

export function compareScenarios(scenarios: Scenario[]) {
  return post<{ results: { name: string; metrics: SimulationResult["metrics"]; bottleneck: SimulationResult["bottleneck"]; funnel: Record<string, number> }[] }>(
    "/api/experiments/compare",
    { scenarios },
  );
}

export function runMonteCarlo(scenario: Scenario, runs: number) {
  return post<{
    runs: number;
    summary: Record<string, { mean: number; median: number; std: number; ci95: [number, number] }>;
    histograms: Record<string, { counts: number[]; edges: number[] }>;
  }>("/api/experiments/monte-carlo", { scenario, runs });
}

export function fetchModel() {
  return fetch("/api/ml/metrics").then((response) => {
    if (!response.ok) throw new Error("Could not load the model report");
    return response.json() as Promise<ModelReport>;
  });
}

export function trainModel() {
  return post<ModelReport>("/api/ml/train", {});
}

export function runOptimization(scenario: Scenario) {
  return post<OptimizationReport>("/api/optimization/run", { scenario, replicates: 6 });
}

export function runCalibration(scenario: Scenario) {
  return post<CalibrationReport>("/api/research/calibrate", { scenario, draws: 80, replicates: 3 });
}

export function runDistressFit(scenario: Scenario) {
  return post<DistressFit>("/api/research/distress", { scenario });
}

export function runPersonaAudit() {
  return post<PersonaAudit>("/api/research/personas", {});
}

export function runSurrogate(scenario: Scenario) {
  return post<SurrogateReport>("/api/research/surrogate", { scenario, initial: 24, steps: 16 });
}

export function runManager(scenario: Scenario) {
  return post<ManagerReport>("/api/research/manager", { scenario, episodes: 48 });
}

export interface CalibrationReport {
  method: string;
  draws: number;
  replicates: number;
  best_distance: number;
  best_summary: Record<string, number>;
  penetration_note: string;
  disclaimer: string;
  targets: { id: string; label: string; value: number; source: string }[];
  posterior: Record<string, { median: number; low: number; high: number }>;
  suggested: Record<string, number>;
}

export interface DistressFit {
  n_completed: number;
  mean_score: number;
  sd_score: number;
  reference_mean: number;
  reference_sd: number;
  share_at_least_4: number;
  benchmark_at_least_4: number;
  share_at_least_8: number;
  benchmark_at_least_8: number;
  total_variation: number;
  ks_statistic: number;
  bins: { score: number; observed: number; reference: number }[];
  mean_source: string;
  tail_source: string;
  note: string;
}

export interface PersonaDecision {
  screening: string;
  disclosure: string;
  nurse: string;
}

export interface PersonaAudit {
  n_pairs: number;
  design: string;
  reading: string;
  rule_outcomes_differ: boolean;
  model_outcomes_differ: boolean | null;
  model_screening_gap: number | null;
  english_accept_rate: number | null;
  punjabi_accept_rate: number | null;
  rows: {
    id: string;
    score: number;
    queue: number;
    english_rules: PersonaDecision;
    punjabi_rules: PersonaDecision;
    english_model: PersonaDecision | null;
    punjabi_model: PersonaDecision | null;
  }[];
}

export interface SurrogateReport {
  method: string;
  evaluations: number;
  candidates: number;
  objective: string;
  disclaimer: string;
  best: { screening_enabled: boolean; referral_threshold: number; n_social_workers: number; n_nurses: number; utility: number };
  trace: { point: string; utility: number; source: string }[];
}

export interface ManagerReport {
  method: string;
  episodes: number;
  learning_curve: number[];
  disclaimer: string;
  policy: { score: string; queue: string; action: string }[];
  evaluation: { runs: number; learned_utility: number; threshold_utility: number; learned_wins: number };
}

export interface ModelReport {
  disclaimer: string;
  n_encounters: number;
  positive_rate: number;
  features: string[];
  shifted?: {
    n_encounters: number;
    positive_rate: number;
    description: string;
    models: { name: string; roc_auc: number; precision: number; recall: number; f1: number }[];
  };
  models: {
    name: string;
    roc_auc: number;
    precision: number;
    recall: number;
    f1: number;
    confusion_matrix: number[][];
    feature_importance: { feature: string; importance: number }[];
  }[];
}

export interface OptimizationReport {
  objective: string;
  replicates: number;
  note: string;
  disclaimer: string;
  current: { nurses: number; social_workers: number; psychologists: number; child_life: number };
  recommended: {
    nurses: number;
    social_workers: number;
    psychologists: number;
    child_life: number;
    feasible: boolean;
    problems: string[];
    mean_wait: number;
    missed: number;
    unserved: number;
    sw_utilization: number;
    mean_psych_wait: number;
  };
  trials: {
    nurses: number;
    social_workers: number;
    psychologists: number;
    feasible: boolean;
    cost: number;
    mean_wait: number;
    missed: number;
    sw_utilization: number;
    problems: string[];
  }[];
}
