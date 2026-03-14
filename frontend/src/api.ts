import type { PredictRequest, PredictResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchSchools(): Promise<string[]> {
  const resp = await fetch(`${API_BASE}/schools`);
  const body = await unwrap<{ values: string[] }>(resp);
  return body.values;
}

export async function fetchMajors(): Promise<string[]> {
  const resp = await fetch(`${API_BASE}/majors`);
  const body = await unwrap<{ values: string[] }>(resp);
  return body.values;
}

export async function predict(payload: PredictRequest): Promise<PredictResponse> {
  const resp = await fetch(`${API_BASE}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return unwrap<PredictResponse>(resp);
}
