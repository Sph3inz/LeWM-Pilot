<script lang="ts">
  import type { TimelineEvent } from '$lib/stores/telemetry';

  const LABELS: Record<string, string> = {
    weather_imc: 'IMC',
    weather_ifr: 'IFR',
    weather_mvfr: 'MVFR',
    weather_vfr: 'VFR',
    environment_change: 'Env change',
    turbulence_burst: 'Turbulence',
    wind_increase: 'Wind+',
    engine_failure: 'Engine',
    attitude_failure: 'Attitude',
    comms_failure: 'Comms',
    hydraulic_leak: 'Hydraulic',
    phase_change: 'Phase'
  };

  let { events = [], simTime = 0 }: { events?: TimelineEvent[]; simTime?: number } = $props();

  const maxT = $derived(Math.max(120, ...events.map((e) => e.effective_time_s), simTime, 1));

  function label(type: string): string {
    return LABELS[type] ?? type.replace(/_/g, ' ');
  }

  function pct(time: number): number {
    return Math.max(1, Math.min(99, (time / maxT) * 100));
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function chipClass(type: string): string {
    if (type.startsWith('weather_') || type.includes('wind') || type.includes('turb')) return 'env';
    if (type.endsWith('_failure') || type === 'hydraulic_leak') return 'fail';
    return 'phase';
  }
</script>

<div class="timeline">
  <div class="duration mono">{formatTime(simTime)} / {formatTime(maxT)}</div>

  <div class="track">
    <div class="rail">
      <div class="progress" style="width: {pct(simTime)}%"></div>
    </div>
    <div class="playhead" style="left: {pct(simTime)}%" aria-hidden="true"></div>
    {#each events as ev}
      <div
        class="pin {chipClass(ev.type)}"
        class:fired={ev.fired}
        style="left: {pct(ev.effective_time_s)}%"
        title="{label(ev.type)} · {formatTime(ev.effective_time_s)}"
      ></div>
    {/each}
  </div>

  {#if events.length}
    <div class="legend">
      {#each events as ev}
        <span class="chip {chipClass(ev.type)}" class:fired={ev.fired}>
          <span class="chip-dot"></span>
          {label(ev.type)}
          <span class="chip-time mono">{formatTime(ev.effective_time_s)}</span>
        </span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .timeline {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }

  .duration {
    font-size: 10px;
    color: var(--text-muted);
    text-align: right;
  }

  .track {
    position: relative;
    height: 22px;
    padding: 0 2px;
  }

  .rail {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: var(--bg-muted);
    border-radius: 2px;
    overflow: hidden;
  }

  .progress {
    height: 100%;
    background: #93c5fd;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .playhead {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 10px;
    height: 10px;
    background: var(--text);
    border: 2px solid var(--bg-surface);
    border-radius: 50%;
    box-shadow: 0 0 0 1px var(--border);
    z-index: 2;
  }

  .pin {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 2px solid var(--bg-surface);
    box-shadow: 0 0 0 1px var(--border);
    z-index: 1;
  }

  .pin.env { background: #0ea5e9; }
  .pin.fail { background: #dc2626; }
  .pin.phase { background: #8b5cf6; }
  .pin.fired { background: #a1a1aa !important; }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    max-height: 72px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding-right: 2px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 7px;
    border-radius: var(--radius-pill);
    background: var(--bg-muted);
    border: 1px solid var(--border-subtle);
    font-size: 10px;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
  }

  .chip.env { border-color: #bae6fd; background: #f0f9ff; }
  .chip.fail { border-color: #fecaca; background: #fef2f2; }
  .chip.phase { border-color: #ddd6fe; background: #f5f3ff; }

  .chip.fired {
    color: var(--text-muted);
    opacity: 0.72;
    background: var(--bg-muted) !important;
    border-color: var(--border-subtle) !important;
  }

  .chip-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
  }

  .chip-time {
    font-size: 9px;
    color: var(--text-muted);
    font-weight: 400;
  }
</style>
