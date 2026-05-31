export interface AdaptationLogEntry {
  sim_time_s: number;
  message: string;
  source: string;
}

export interface TimelineEvent {
  type: string;
  time_offset_s: number;
  effective_time_s: number;
  fired: boolean;
}

export interface TelemetryFrame {
  type: string;
  session_id: string;
  timestamp_ns?: number;
  sim_time_s: number;
  aircraft_id: string;
  position: { x_m: number; y_m: number };
  lat_deg?: number | null;
  lon_deg?: number | null;
  alt_ft: number;
  pitch_deg?: number;
  roll_deg?: number;
  ias_kt: number;
  heading_deg: number;
  pilot_score: number;
  score_band: string;
  active_failures: string[];
  scenario_events_pending: number;
  adaptation_log: AdaptationLogEntry[];
  timeline: { events?: TimelineEvent[] };
  environment?: {
    crosswind_kt?: number;
    gust_factor?: number;
    turbulence_index?: number;
    visibility_sm?: number;
    ceiling_ft?: number;
  };
}

import { writable } from 'svelte/store';

export const latestFrame = writable<TelemetryFrame | null>(null);
export const frameHistory = writable<TelemetryFrame[]>([]);
export const connectionState = writable<'connecting' | 'open' | 'closed'>('connecting');
export const plannerBackend = writable<'lewm' | 'mock' | null>(null);
export const plannerDevice = writable<string | null>(null);

const WS_URL = 'ws://localhost:8765/ws/session';
const API_URL = 'http://localhost:8765';
const MAX_HISTORY = 2400;

let ws: WebSocket | null = null;
let reconnectDelay = 1000;

export async function fetchServerHealth() {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) return;
    const data = (await res.json()) as {
      planner_backend?: string;
      planner_device?: string;
    };
    const backend = data.planner_backend === 'lewm' ? 'lewm' : data.planner_backend === 'mock' ? 'mock' : null;
    plannerBackend.set(backend);
    plannerDevice.set(data.planner_device ?? null);
  } catch {
    plannerBackend.set(null);
    plannerDevice.set(null);
  }
}

export function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }
  connectionState.set('connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    connectionState.set('open');
    reconnectDelay = 1000;
    void fetchServerHealth();
  };

  ws.onclose = () => {
    connectionState.set('closed');
    ws = null;
    setTimeout(connectWebSocket, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };

  ws.onmessage = (ev) => {
    const frame = JSON.parse(ev.data) as TelemetryFrame;
    if (frame.type !== 'telemetry') return;
    latestFrame.set(frame);
    frameHistory.update((hist) => {
      if (hist.length > 0) {
        const last = hist[hist.length - 1];
        if (last.session_id !== frame.session_id) {
          return [frame];
        }
        // Genuine episode rollover only (not clock noise)
        if (
          frame.sim_time_s + 8 < last.sim_time_s &&
          frame.sim_time_s < 3 &&
          last.sim_time_s > 90
        ) {
          return [frame];
        }
      }
      const next = [...hist, frame];
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
    });
  };
}

export function sendUpstream(msg: Record<string, unknown>) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}
