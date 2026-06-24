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
  created_at: string;
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
  finished_at?: string | null;
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
}

export interface Analytics {
  total_assets: number;
  unique_objects: number;
  dedup_savings_pct: number;
  images: number;
  videos: number;
  estimated_cost_usd: number;
  provider_mix: Record<string, number>;
  fallback_rate: number;
}
