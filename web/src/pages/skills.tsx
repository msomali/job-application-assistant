import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const topQuery = useQuery({
    queryKey: queryKeys.skills.top(20),
    queryFn: () => apiClient.get("/api/skills/top?limit=20").then((r) => r.data),
    staleTime: 120_000,
  });

  const gapsQuery = useQuery({
    queryKey: queryKeys.skills.gaps,
    queryFn: () => apiClient.get("/api/skills/gaps").then((r) => r.data),
    staleTime: 120_000,
  });

  const trendsQuery = useQuery({
    queryKey: queryKeys.skills.trends,
    queryFn: () => apiClient.get("/api/skills/trends").then((r) => r.data),
    staleTime: 120_000,
  });

  const rolesQuery = useQuery({
    queryKey: queryKeys.skills.roles,
    queryFn: () => apiClient.get("/api/skills/roles").then((r) => r.data),
    staleTime: 120_000,
  });

  return (
    <div className="grid grid-cols-2 gap-5">
      {/* Top skills bar chart */}
      <Card className="col-span-2">
        <CardHeader><CardTitle className="text-base">Top Requested Skills</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={topQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No skill data yet. Analyze some jobs first.</p>}
          >
            {(data: any[]) => (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="skill" tick={{ fontSize: 12 }} width={80} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </QueryState>
        </CardContent>
      </Card>

      {/* Skill gaps table */}
      <Card>
        <CardHeader><CardTitle className="text-base">Skill Gaps</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={gapsQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No gaps detected. Update your profile skills to see gaps.</p>}
          >
            {(data: any[]) => (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Skill</TableHead>
                    <TableHead className="text-right">Demand</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.slice(0, 15).map((gap: any) => (
                    <TableRow key={gap.skill}>
                      <TableCell className="font-medium">{gap.skill}</TableCell>
                      <TableCell className="text-right">{gap.demand_count} jobs</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryState>
        </CardContent>
      </Card>

      {/* Trends line chart */}
      <Card>
        <CardHeader><CardTitle className="text-base">Skill Trends</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={trendsQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">Not enough data for trends yet.</p>}
          >
            {(data: any[]) => {
              const weekMap = new Map<string, number>();
              for (const d of data) {
                const week = d.week.slice(0, 10);
                weekMap.set(week, (weekMap.get(week) ?? 0) + d.count);
              }
              const chartData = Array.from(weekMap.entries())
                .map(([week, count]) => ({ week, count }))
                .sort((a, b) => a.week.localeCompare(b.week));

              return (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              );
            }}
          </QueryState>
        </CardContent>
      </Card>

      {/* Roles breakdown */}
      <Card className="col-span-2">
        <CardHeader><CardTitle className="text-base">Skills by Role Level</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={rolesQuery}
            isEmpty={(data: any) => Object.keys(data).length === 0}
            empty={<p className="text-sm text-muted-foreground">No role data available.</p>}
          >
            {(data: any) => (
              <div className="grid grid-cols-3 gap-4">
                {Object.entries(data).map(([level, skills]: [string, any]) => (
                  <div key={level}>
                    <h4 className="mb-2 text-sm font-semibold capitalize">{level}</h4>
                    <div className="space-y-1">
                      {skills.slice(0, 8).map((s: any) => (
                        <div key={s.skill} className="flex items-center justify-between text-xs">
                          <span>{s.skill}</span>
                          <span className="text-muted-foreground">{s.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
