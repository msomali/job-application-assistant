export const queryKeys = {
  jobs: {
    all: ["jobs"] as const,
    list: (params: Record<string, unknown>) => ["jobs", params] as const,
    detail: (id: number) => ["jobs", id] as const,
    ranked: (limit?: number) => ["jobs", "ranked", limit] as const,
  },
  analysis: {
    byJob: (jobId: number) => ["analysis", jobId] as const,
  },
  documents: {
    byJob: (jobId: number) => ["documents", jobId] as const,
  },
  profile: {
    current: ["profile"] as const,
  },
  discovery: {
    configs: ["discovery", "configs"] as const,
  },
  search: {
    results: (params: Record<string, unknown>) => ["search", params] as const,
  },
  skills: {
    top: (limit?: number) => ["skills", "top", limit] as const,
    gaps: ["skills", "gaps"] as const,
    trends: ["skills", "trends"] as const,
    roles: ["skills", "roles"] as const,
  },
  answers: {
    all: ["answers"] as const,
    list: (params: Record<string, unknown>) => ["answers", params] as const,
    stats: ["answers", "stats"] as const,
  },
  billing: {
    plan: ["billing", "plan"] as const,
    usage: ["billing", "usage"] as const,
    history: (days?: number) => ["billing", "history", days] as const,
    invoices: ["billing", "invoices"] as const,
  },
  tasks: {
    all: ["tasks"] as const,
    detail: (id: string) => ["tasks", id] as const,
  },
  admin: {
    users: ["admin", "users"] as const,
  },
};
