/** Shapes the API actually returns. Mirrors api/schemas.py and the tool payloads. */

export interface Fact {
  id: string;
  label: string;
  value: number | string;
  unit: string;
  source: string;
}

export interface KelurahanProperties {
  kel_id: string;
  kel_name: string;
  kec_id: string;
  kec_name: string;
  kota_id: string;
  kota_name: string;
  lst_c_mean: number | null;
  lst_anomaly_c: number | null;
  hvi: number | null;
  hvi_rank: number | null;
  H: number | null;
  E: number | null;
  S: number | null;
  A: number | null;
  ndvi_mean: number | null;
  tree_frac_mean: number | null;
  built_frac_mean: number | null;
  pop: number | null;
  pop_density: number | null;
  exposed_vulnerable: number | null;
  /**
   * Injected client-side by the scenario dock after a simulation, not part of the API
   * payload. Drives the ΔLST map layer; null means the kelurahan was not simulated.
   */
  delta_lst_c?: number | null;
}

export interface KelurahanFeature {
  type: 'Feature';
  properties: KelurahanProperties;
  geometry: { type: 'MultiPolygon'; coordinates: number[][][][] };
}

export interface KelurahanCollection {
  type: 'FeatureCollection';
  features: KelurahanFeature[];
  attribution: string;
}

export interface Driver {
  feature: string;
  label: string;
  contribution_c: number;
  direction: 'memanaskan' | 'mendinginkan';
}

export interface AreaProfile {
  kel_id: string;
  kel_name: string;
  kec_name: string;
  kota_name: string;
  lst: number;
  lst_anomaly: number;
  hvi: number;
  hvi_rank: number;
  ndvi: number;
  tree_frac: number;
  built_frac: number;
  water_frac: number;
  pop: number;
  vulnerable: number;
  exposed_vulnerable: number;
  H: number;
  E: number;
  S: number;
  A: number;
}

export interface ProfileResponse {
  profile: AreaProfile;
  total_kelurahan: number;
  note: string;
  drivers: Driver[];
  drivers_unavailable?: string;
  facts: Fact[];
}

export type InterventionType = 'tree_planting' | 'cool_roof' | 'green_roof';
export type Level = 'low' | 'medium' | 'high';

export interface InterventionInput {
  type: InterventionType;
  level?: Level;
  params?: Record<string, number>;
}

export interface ScenarioResult {
  kel_id: string;
  delta_lst_c: number;
  delta_lst_pop_weighted_c: number;
  vulnerable_benefiting: number;
  area_m2: number;
  area_by_type: Record<string, number>;
  cost_idr: number;
  extrapolation: boolean;
  extrapolated_features: string[];
  n_cells: number;
}

export interface EvidenceEntry {
  id: string;
  intervention: string;
  metric: string;
  value_min: number;
  value_max: number;
  unit: string;
  context: string;
  source_title: string;
  year: number | null;
  url_or_doi: string;
  comparable_to_model: boolean;
}

export interface SimulateResponse {
  results: ScenarioResult[];
  interventions: InterventionInput[];
  evidence: EvidenceEntry[];
  note: string;
  map_highlight: string[];
  facts: Fact[];
}

export interface PortfolioPackage {
  kel_id: string;
  kel_name: string;
  intervention_type: InterventionType;
  level: Level;
  cost_idr: number;
  delta_lst_c: number;
  vulnerable_benefiting: number;
  area_m2: number;
  in_top_hvi_quintile: boolean;
}

export interface OptimizeResponse {
  packages: PortfolioPackage[];
  total_cost_idr: number;
  budget_idr: number;
  equity_share_requested: number;
  equity_share_achieved: number;
  solver_status: string;
  note: string;
  map_highlight: string[];
  facts: Fact[];
}

export interface ModelCard {
  version: string;
  target: string;
  target_caveat: string;
  data_period: string;
  area: string;
  n_train_cells: number;
  n_kelurahan: number;
  features: string[];
  validation: {
    scheme: string;
    why: string;
    summary: { r2_mean: number; r2_min: number; rmse_mean: number; mae_mean: number };
    target_r2: number;
    meets_target: boolean;
  };
  independent_checks: Record<string, string>;
  limitations: string[];
}

export interface RoofAnalysis {
  roof_visible: boolean;
  roof_form: 'flat' | 'pitched' | 'mixed' | 'unknown';
  material: string;
  color_tone: 'light' | 'medium' | 'dark';
  condition: string;
  shade_from_trees: 'none' | 'partial' | 'heavy';
  confidence: number;
  notes: string;
}

export interface RoofRecommendation {
  action: string;
  priority: string;
  reason: string;
  safety: string[];
  evidence_ids: string[];
}

export interface RoofResponse {
  roof: RoofAnalysis;
  recommendation: RoofRecommendation;
  evidence: EvidenceEntry[];
  guidance: string;
  kelurahan: string | null;
  facts: Fact[];
}
