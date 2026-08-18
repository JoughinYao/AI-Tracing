export type Source = {
  source_name: string;
  display_name: string;
  default_category: string;
  enabled: boolean;
  source_type: string;
  source_origin: string;
  crawl_strategy: string;
  source_url?: string | null;
  latest_status?: string | null;
  latest_checked_at?: string | null;
  last_success_at?: string | null;
  last_checkpoint_at?: string | null;
  last_error?: string | null;
  crawler_config: Record<string, unknown>;
  synced_to_crawler_at?: string | null;
};

export type Item = {
  id: number;
  external_id: string;
  source_name: string;
  source_origin: string;
  source_type: string;
  source_url?: string | null;
  original_url?: string | null;
  title: string;
  summary?: string | null;
  category?: string | null;
  company?: string | null;
  domain?: string | null;
  event_type?: string | null;
  entities: string[];
  tags: string[];
  published_at?: string | null;
  author?: string | null;
  language?: string | null;
  content_hash?: string | null;
  content_excerpt?: string | null;
  canonical_key?: string | null;
  product_key?: string | null;
  model_key?: string | null;
  version_key?: string | null;
  related_official_item_id?: number | null;
  relation_type?: string | null;
  relation?: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  llm_status: string;
  processing_status: string;
  key_points: string[];
  technical_details: Array<Record<string, unknown>>;
  value_interpretation?: Record<string, unknown> | null;
  impact_scope: string[];
  risk_or_limitations: string[];
  recommended_action?: string | null;
  evidence_excerpts: Array<Record<string, unknown>>;
  information_gaps: string[];
  content_depth?: string | null;
  primary_image?: Record<string, unknown> | null;
  image_candidates: Array<Record<string, unknown>>;
  comments: ContentComment[];
  related_third_party: RelatedThirdParty[];
  crawl_batch_id?: number | null;
  created_at: string;
};

export type ContentComment = {
  id: number;
  official_item_id: number;
  third_party_item_id?: number | null;
  source_name: string;
  original_url?: string | null;
  title: string;
  summary?: string | null;
  sentiment: string;
  relation_type: string;
  published_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type RelatedThirdParty = {
  relation_type: string;
  relation_confidence?: string | null;
  relation_reason?: string | null;
  title: string;
  summary?: string | null;
  author?: string | null;
  published_at?: string | null;
  source_name: string;
  source_display_name: string;
  original_url?: string | null;
  sentiment: string;
};

export type RelationUpdate = {
  official_item_id: number;
  official_internal_id: string;
  official_title: string;
  last_relation_added_at: string;
  relation_update_count_today: number;
  latest_relation_title?: string | null;
  latest_relation_source_name?: string | null;
  latest_relation_source_display_name?: string | null;
};

export type Batch = {
  id: number;
  batch_date: string;
  status: string;
  triggered_at: string;
  finished_at?: string | null;
  total_sources: number;
  success_sources: number;
  failed_sources: number;
  top6_count: number;
  raw_count: number;
  saved_count: number;
  comment_attached_count: number;
  duplicate_dropped_count: number;
  notes?: string | null;
};

export type HomeTodayResponse = {
  report_date: string;
  has_updates: boolean;
  is_empty: boolean;
  status_text: string;
  batch?: Batch | null;
  relation_updates: RelationUpdate[];
  top6: Item[];
  sources: Source[];
};

export type ItemPage = {
  items: Item[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type MetricsPoint = {
  snapshot_at: string;
  stars?: number | null;
  forks?: number | null;
  watchers?: number | null;
  subscribers?: number | null;
  open_issues?: number | null;
  pushed_at?: string | null;
  updated_at?: string | null;
};

export type MetricsResponse = {
  source_name: string;
  series: MetricsPoint[];
};

export type AgentMetricsSeries = {
  source_name: string;
  display_name: string;
  series: MetricsPoint[];
};

export type CoreAgentMetricsResponse = {
  range: "all" | "week" | "month";
  agents: AgentMetricsSeries[];
};

export type SystemLog = {
  id: number;
  log_date: string;
  level: string;
  source_name?: string | null;
  action: string;
  message: string;
  context: Record<string, unknown>;
};
