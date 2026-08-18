import type { Batch, CoreAgentMetricsResponse, HomeTodayResponse, ItemPage, Source, SystemLog } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let message = `request failed: ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // Keep the status-based message when the response body is not JSON.
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  homeToday: () => fetchJson<HomeTodayResponse>("/api/home/today"),
  items: (params: { section: string; date?: string; page: number; page_size: number }) => {
    const search = new URLSearchParams({
      section: params.section,
      page: String(params.page),
      page_size: String(params.page_size),
    });
    if (params.date) search.set("date", params.date);
    return fetchJson<ItemPage>(`/api/items?${search.toString()}`);
  },
  coreAgentMetrics: (params: { range?: "all" | "week" | "month" }) => {
    const search = new URLSearchParams();
    if (params.range) search.set("range", params.range);
    return fetchJson<CoreAgentMetricsResponse>(`/api/core-agent/metrics?${search.toString()}`);
  },
  systemLogs: (params?: string | { date?: string; days?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (typeof params === "string") {
      search.set("date", params);
    } else {
      if (params?.date) search.set("date", params.date);
      if (params?.days) search.set("days", String(params.days));
      if (params?.page_size) search.set("page_size", String(params.page_size));
    }
    return fetchJson<SystemLog[]>(`/api/system-logs?${search.toString()}`);
  },
  crawlBatches: () => fetchJson<Batch[]>("/api/crawl-batches"),
  sources: () => fetchJson<Source[]>("/api/sources"),
  createGithubSource: (payload: { source_name: string; repo_url: string; is_official: boolean }) =>
    fetchJson<Source>("/api/sources/github-repository", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  createThirdPartySource: (payload: {
    source_name: string;
    source_url: string;
    platform: string;
    list_container_xpath: string;
    article_url_regex: string;
    default_max_candidates: number;
    default_max_items: number;
    default_max_pages: number;
    render_list_page: boolean;
    render_article_page: boolean;
    source_tags: string[];
    blocked_url_keywords: string[];
  }) =>
    fetchJson<Source>("/api/sources/third-party", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  runBatch: (sourceNames?: string[]) =>
    fetchJson<{ batch_id: number; status: string; message: string; top6_count: number }>("/api/crawl-batches/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sourceNames?.length ? { source_names: sourceNames } : { source_name: "all" }),
    }),
  rerankTop6: () =>
    fetchJson<{ batch_id: number; status: string; message: string; top6_count: number }>("/api/crawl-batches/rerank", {
      method: "POST",
    }),
};
