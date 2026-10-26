export type RunKind = 'tournament' | 'moran' | 'trust';
export type Config = {
  theta: number; alpha_pos: number; alpha_neg: number; delta: number;
  threshold: number; variant: string; seed: number;
  rounds: number; repetitions: number; opponents: string[]; presets: string[];
  extra_opponent: string; noise_wrap: boolean; noise_pct: number;
  generations: number; population: number; send: number;
  return_good: number; return_bad: number; betrayal_probability: number;
};
export type Catalogue = {
  variants: string[]; opponents: string[]; extra_opponents: string[];
  presets: Record<string, { creator?: string; description?: string; theta: number; alpha_pos: number; alpha_neg: number; delta: number; tau: number; variant?: string }>;
  submissions_enabled: boolean; version: string; max_run_seconds: number;
};
export type Result = {
  kind: RunKind; config: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  leaderboard?: Record<string, string | number | null>[]; players?: string[];
  scores?: number[][]; payoff_matrix?: number[][]; wins?: number[][];
  series?: number[]; payoffs?: number[]; cumulative?: number[]; investments?: number[];
  summary?: Record<string, number | null>;
};
export type StreamEvent = {
  type: 'started' | 'progress' | 'heartbeat' | 'result' | 'error';
  phase?: string; percent?: number | null; completed?: number; total?: number;
  message?: string; elapsed?: number; result?: Result;
};
export const DEFAULT_CONFIG: Config = {
  theta: .6, alpha_pos: .02, alpha_neg: .675, delta: .45, threshold: .5, variant: 'TFT', seed: 42,
  rounds: 200, repetitions: 30,
  opponents: ['Tit For Tat', 'Defector', 'Win-Stay Lose-Shift', 'Random', 'ZD-Extort-2', 'EvolvedLookerUp2_2_2', 'AON2', 'Adaptive Pavlov 2011', 'Meta Hunter'],
  presets: [], extra_opponent: 'None', noise_wrap: false, noise_pct: 0,
  generations: 200, population: 20, send: 5, return_good: .5, return_bad: 0, betrayal_probability: 0,
};
export function payload(kind: RunKind, config: Config): Record<string, unknown> {
  const base = Object.fromEntries(['theta', 'alpha_pos', 'alpha_neg', 'delta', 'threshold', 'variant', 'seed'].map(key => [key, config[key as keyof Config]]));
  const keys = kind === 'tournament'
    ? ['rounds', 'repetitions', 'opponents', 'presets', 'extra_opponent', 'noise_wrap', 'noise_pct']
    : kind === 'moran' ? ['rounds', 'generations', 'population']
    : ['rounds', 'send', 'return_good', 'return_bad', 'betrayal_probability'];
  return { ...base, ...Object.fromEntries(keys.map(key => [key, config[key as keyof Config]])) };
}
export async function jsonHeaders(body: string): Promise<Record<string, string>> {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body));
  return { 'Content-Type': 'application/json', 'x-amz-content-sha256': Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('') };
}
export async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item: { msg: string }) => item.msg.replace(/^Value error, /, '')).join(' ');
  } catch { /* Fall through to a readable status. */ }
  return response.status === 429 ? 'The demo is busy. Please try again shortly.' : `The request could not complete (${response.status}). Please try again.`;
}

/** Decode across arbitrary UTF-8/network chunk boundaries; EOF is not success. */
export async function readEvents(body: ReadableStream<Uint8Array>, onEvent: (event: StreamEvent) => void): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', terminal = false;
  function line(value: string) {
    if (!value.trim()) return;
    if (terminal) throw new Error('Unexpected data after the simulation finished.');
    const event = JSON.parse(value) as StreamEvent;
    if (!['started', 'progress', 'heartbeat', 'result', 'error'].includes(event.type)) throw new Error('Unrecognized simulation response.');
    if (event.type === 'result' && !event.result) throw new Error('The simulation result is missing.');
    terminal = event.type === 'result' || event.type === 'error';
    onEvent(event);
    if (event.type === 'error') throw new Error(event.message || 'The simulation could not finish.');
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf('\n')) >= 0) {
        const value = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 1); line(value);
      }
      if (buffer.length > 8_000_000) throw new Error('The simulation response is too large.');
      if (done) { if (buffer.trim()) line(buffer); break; }
    }
    if (!terminal) throw new Error('The connection ended before a result arrived. Your run cannot be resumed; you can start it again with the same settings.');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function csv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return '';
  const columns = Object.keys(rows[0]);
  const quote = (value: unknown) => {
    let text = String(value ?? '');
    // Prevent spreadsheet formula execution for any exported string label.
    if (typeof value === 'string' && /^[=+@\-\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return [columns.map(quote).join(','), ...rows.map(row => columns.map(key => quote(row[key])).join(','))].join('\r\n');
}
export function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
