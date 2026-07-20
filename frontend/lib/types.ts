export type Style = "original" | "studio" | "lifestyle" | "onmodel" | "variant" | "video";
export type Modality = "image" | "video";
export type JobStatus = "queued" | "running" | "partial" | "done" | "failed";
export type Marketplace = "amazon" | "etsy" | "shopify" | "ebay" | "social";

export interface BrandKit {
  vibe?: string | null;
  lighting?: string | null;
  palette?: string | null;
  props?: string | null;
  notes?: string | null;
}

export interface Sku {
  id: string;
  owner_uid: string;
  title: string;
  category?: string | null;
  description?: string | null;
  original_sha256?: string | null;
  created_at: string;
}

export interface Asset {
  id: string;
  sku_id: string;
  owner_uid: string;
  sha256: string;
  url?: string | null;
  modality: Modality;
  style: Style;
  is_authentic: boolean;
  parent_sha256?: string | null;
  run_id?: string | null;
  provider?: string | null;
  model?: string | null;
  manifest_key?: string | null;
  embedded?: boolean;
  mime_type?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  qa?: QAReport | null;
  /** SHA-256 of the asset this one was replayed from (its manifest supplied the spec). */
  replay_of?: string | null;
  created_at: string;
}

export interface ListingEntry {
  title: string;
  description: string;
  bullets: string[];
  keywords: string[];
  title_max: number;
}

export interface Listing {
  generated_at: string;
  provider: string;
  model: string;
  disclosure: string;
  marketplaces: Record<string, ListingEntry>;
}

export interface QACheck {
  name: string;
  passed: boolean;
  value?: string | number;
  threshold?: string | number;
  detail?: string;
}

export interface QAReport {
  passed: boolean;
  checks: QACheck[];
  scorer: "deterministic" | "deterministic+vlm";
  vlm_score?: number | null;
  vlm_verdict?: string | null;
  attempt?: number;
  attempts?: number;
}

export type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface JobStep {
  style: Style;
  status: StepStatus;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  eta_seconds?: number | null;
  provider?: string | null;
  model?: string | null;
  cost_usd?: number | null;
  asset_count: number;
  error?: string | null;
  qa_passed?: boolean | null;
  qa_attempts?: number | null;
}

export interface Job {
  id: string;
  owner_uid: string;
  sku_id: string;
  status: JobStatus;
  requested_styles: Style[];
  marketplaces?: Marketplace[];
  asset_ids: string[];
  cost_estimate?: number | null;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  steps: JobStep[];
  eta_seconds?: number | null;
  credits_held?: number | null;
  cost_actual?: number | null;
  /** Set when the job is a replay: hash of the asset whose manifest is re-executed. */
  replay_of_sha256?: string | null;
}

export interface VerifyResult {
  sha256: string;
  found: boolean;
  verified: boolean;
  is_authentic: boolean;
  embedded?: boolean;
  content_bound?: boolean | null;
  modality?: Modality | null;
  style?: Style | null;
  provider?: string | null;
  model?: string | null;
  parent_sha256?: string | null;
  created_at?: string | null;
  disclosure: string;
  /** Null means "not in the log" — appends are best-effort, so that is not a negative. */
  ledger?: LedgerPosition | null;
  /**
   * "Verify in the Wild": set only when the cryptographic tiers found nothing but the image
   * is perceptually close to a known asset (a re-encoded marketplace copy whose manifest was
   * stripped). Evidence, never proof — never sets content_bound. See app/models.py.
   */
  perceptual?: PerceptualMatch | null;
}

/** A perceptual (visual-similarity) match — the third verify tier. Mirrors app/models.py. */
export interface PerceptualMatch {
  matched_sha256: string;
  /** Hamming distance over the 64-bit pHash (0 = identical). The honest signal. */
  distance: number;
  /** 0–1, for display only; `distance` is the real signal. */
  confidence: number;
  /** distance <= the confident-match threshold. */
  strong: boolean;
  style?: Style | null;
  provider?: string | null;
  model?: string | null;
  parent_sha256?: string | null;
  matched_in_ledger?: boolean;
}

/** Transparency log — append-only hash chain. Mirrors app/models.py. */
export interface LedgerPosition {
  seq: number;
  entry_hash: string;
  recorded_at: string;
  log_size: number;
  checkpoint_hash?: string | null;
  checkpoint_size?: number | null;
  checkpoint_covers_entry: boolean;
}

export interface LedgerCheckpoint {
  log_id: string;
  size: number;
  head: string;
  issued_at: string;
  checkpoint_hash: string;
  b2_key?: string | null;
}

export interface LedgerStatus {
  log_id: string;
  size: number;
  head: string;
  checkpoint?: LedgerCheckpoint | null;
  checkpoint_lag: number;
}

export interface LedgerAuditFailure {
  sha256: string;
  style?: string | null;
  kind?: string;
  checks?: Record<string, boolean>;
  error?: string | null;
}

/** One pass of the scheduled integrity agent (GET /api/ledger/audit). */
export interface LedgerAudit {
  audit_id: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  assets_sampled: number;
  assets_passed: number;
  failures: LedgerAuditFailure[];
  ledger_entries: number;
  chain_consistent?: boolean | null;
  checkpoint_reproduced?: boolean | null;
  checkpoint?: LedgerCheckpoint | null;
  b2_key?: string | null;
  sha256?: string | null;
  caveat: string;
}

export interface LedgerEntryRow {
  seq: number;
  prev_hash: string;
  subject_sha256: string;
  manifest_hash: string;
  kind: string;
  recorded_at: string;
  entry_hash: string;
}

/** Catalog Mode — one generation run across many SKUs. Mirrors app/models.py. */
export type BatchStatus = "queued" | "running" | "done" | "partial" | "failed";
export type BatchItemStatus =
  | "pending"
  | "running"
  | "done"
  | "partial"
  | "failed"
  | "blocked";

export interface BatchItem {
  sku_id: string;
  title?: string | null;
  job_id?: string | null;
  status: BatchItemStatus;
  asset_count: number;
  cost_actual?: number | null;
  duration_ms?: number | null;
  error?: string | null;
}

export interface Batch {
  id: string;
  owner_uid: string;
  title?: string | null;
  status: BatchStatus;
  styles: Style[];
  marketplaces: Marketplace[];
  items: BatchItem[];
  concurrency: number;
  cost_estimate?: number | null;
  cost_actual?: number | null;
  eta_seconds?: number | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface BatchEstimate {
  skus: number;
  styles: Style[];
  per_sku_usd: number;
  total_estimate_usd: number;
  balance_usd: number;
  affordable: boolean;
  eta_seconds: number;
  quota_remaining: number;
  basis: string;
}

/** Resolve — dispute evidence. Mirrors app/models.py::ResolveOut. */
export type ResolveFinding =
  | "listing_tampered"
  | "item_mismatch"
  | "condition_differences"
  | "inconclusive"
  | "no_provenance"
  | "provenance_only"
  | "consistent";

export type ResolveSeverity = "critical" | "warning" | "info" | "ok";

export interface ResolveReport {
  id: string;
  issued_at: string;
  finding: ResolveFinding;
  severity: ResolveSeverity;
  headline: string;
  detail: string;
  listing: {
    sha256?: string | null;
    present: boolean;
    verified: boolean;
    content_bound?: boolean | null;
    found: boolean;
    is_authentic: boolean;
    provider?: string | null;
    model?: string | null;
    created_at?: string | null;
  };
  anchor?: { sha256?: string | null; created_at?: string | null } | null;
  received?: { sha256?: string | null } | null;
  match?: {
    score: number;
    verdict: string;
    differences: string[];
    model: string;
  } | null;
  match_unavailable?: string | null;
  report_sha256?: string | null;
  report_url?: string | null;
}

export interface Analytics {
  total_assets: number;
  unique_objects: number;
  dedup_savings_pct: number;
  images: number;
  videos: number;
  actual_cost_usd: number;
  estimated_cost_usd: number;
  cost_source: string;
  provider_mix: Record<string, number>;
  fallback_rate: number;
}

// ── Users & roles ─────────────────────────────────────────────────────
export type Role = "customer" | "seller" | "admin";

export interface Me {
  uid: string;
  email?: string | null;
  username?: string | null;
  roles: Role[];
  created_at: string;
  updated_at?: string | null;
  credits_balance: number;
}

// ── Credits ───────────────────────────────────────────────────────────
export type LedgerKind = "grant" | "hold" | "debit" | "refund" | "adjust";

export interface LedgerEntry {
  id: string;
  uid: string;
  kind: LedgerKind;
  amount_usd: number;
  balance_after: number;
  seq: number;
  job_id?: string | null;
  sku_id?: string | null;
  note?: string | null;
  actor_uid?: string | null;
  created_at: string;
}

export interface CreditSummary {
  balance_usd: number;
  granted_total_usd: number;
  spent_total_usd: number;
  held_usd: number;
  daily_quota: number;
  daily_used: number;
  low_balance: boolean;
}

export interface CostEstimate {
  styles: {
    style: Style;
    outputs: number;
    estimate_usd: number;
    eta_seconds: number;
  }[];
  total_estimate_usd: number;
  eta_seconds: number;
  balance_usd: number;
  affordable: boolean;
  basis: string;
}

// ── Admin ─────────────────────────────────────────────────────────────
export interface AdminUserRow {
  uid: string;
  email?: string | null;
  username?: string | null;
  roles: Role[];
  credits_balance: number;
  credits_spent_total: number;
  skus: number;
  assets: number;
  jobs: number;
  last_active?: string | null;
  created_at?: string | null;
}

export interface AdminJobRow {
  id: string;
  owner_uid: string;
  owner_email?: string | null;
  sku_id: string;
  status: JobStatus;
  requested_styles: Style[];
  asset_count: number;
  cost_actual?: number | null;
  duration_ms?: number | null;
  error?: string | null;
  created_at: string;
}

export interface B2Stats {
  backend: string;
  bucket?: string | null;
  region?: string;
  objects: number;
  bytes: number;
  by_prefix?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

export interface ProviderBudget {
  budget_usd: number;
  metered_spend_usd: number;
  remaining_usd: number;
  configured: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
  /** GMI exposes no balance endpoint to an inference key — always false today. */
  provider_api_supports_balance: boolean;
  source: string;
}

export interface AdminOverview {
  users_total: number;
  users_active_7d: number;
  skus_total: number;
  assets_total: number;
  jobs_total: number;
  jobs_succeeded: number;
  jobs_partial: number;
  jobs_failed: number;
  success_rate_pct: number;
  p50_duration_ms?: number | null;
  p95_duration_ms?: number | null;
  spend_total_usd: number;
  credits_outstanding_usd: number;
  credits_granted_usd: number;
  images: number;
  videos: number;
  provider_mix: Record<string, number>;
  dedup_savings_pct: number;
  embedded_pct: number;
  b2: B2Stats;
  generated_24h: number;
  provider_budget?: ProviderBudget | null;
}

export interface ServiceCheck {
  name: string;
  ok: boolean;
  detail?: string | null;
  latency_ms?: number | null;
}

export interface AdminHealth {
  status: string;
  env: string;
  checks: ServiceCheck[];
  job_queue: string;
  generation_mode: string;
  providers: Record<string, boolean>;
  manifest_embed_mode: string;
  uptime_seconds: number;
  version: string;
}
