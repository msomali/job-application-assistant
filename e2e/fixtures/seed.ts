import axios from "axios";

const API_URL = "http://localhost:8000";

export async function seedJobs(accessToken: string, count: number = 3) {
  const headers = { Authorization: `Bearer ${accessToken}` };
  const resp = await axios.get(`${API_URL}/api/jobs?limit=1`, { headers });
  if (resp.data.length > 0) return;
}

export async function seedSearchConfig(accessToken: string) {
  const headers = { Authorization: `Bearer ${accessToken}` };
  await axios.post(
    `${API_URL}/api/discovery/configs`,
    { name: "Test Config", config_type: "search_query", config: { query: "test", location: "Remote" } },
    { headers },
  );
}
