<script lang="ts">
  import { latestFrame, frameHistory } from '$lib/stores/telemetry';
  import ScoreGauge from '$lib/components/ScoreGauge.svelte';
  import ScoreHistory from '$lib/components/ScoreHistory.svelte';
  import ScenarioTimeline from '$lib/components/ScenarioTimeline.svelte';
  import AdaptationLog from '$lib/components/AdaptationLog.svelte';
  import FlightCanvas from '$lib/components/FlightCanvas.svelte';
  import FlightView3D from '$lib/components/FlightView3D.svelte';
  import FailureOverridePanel from '$lib/components/FailureOverridePanel.svelte';

  let flightView: '3d' | '2d' = $state('3d');

  const band = $derived($latestFrame?.score_band ?? 'moderate');
  const scorePct = $derived(Math.round(($latestFrame?.pilot_score ?? 0) * 100));
</script>

<div class="dash">
  <!-- KPI strip -->
  <div class="kpi-strip panel">
    <div class="kpi">
      <span class="kpi-label">Pilot score</span>
      <span class="kpi-value">{scorePct}<small>%</small></span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Band</span>
      <span class="kpi-value band-{band}">{band}</span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Altitude</span>
      <span class="kpi-value">{$latestFrame ? $latestFrame.alt_ft.toFixed(0) : '—'}<small> ft</small></span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Airspeed</span>
      <span class="kpi-value">{$latestFrame ? $latestFrame.ias_kt.toFixed(0) : '—'}<small> kt</small></span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Events pending</span>
      <span class="kpi-value">{$latestFrame?.scenario_events_pending ?? 0}</span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Wind</span>
      <span class="kpi-value kpi-sm">{$latestFrame?.environment?.crosswind_kt?.toFixed(0) ?? '—'}<small> kt</small></span>
    </div>
    <div class="kpi-divider"></div>
    <div class="kpi">
      <span class="kpi-label">Vis / ceiling</span>
      <span class="kpi-value kpi-sm">
        {$latestFrame?.environment?.visibility_sm?.toFixed(1) ?? '—'}<small> sm</small>
        · {$latestFrame?.environment?.ceiling_ft?.toFixed(0) ?? '—'}<small> ft</small>
      </span>
    </div>
  </div>

  <!-- Main grid: flight + performance -->
  <div class="grid-main">
    <section class="panel panel-flight">
      <div class="panel-head">
        <h2>Flight view</h2>
        <div class="view-toggle">
          <button type="button" class:active={flightView === '3d'} onclick={() => (flightView = '3d')}>3D</button>
          <button type="button" class:active={flightView === '2d'} onclick={() => (flightView = '2d')}>2D</button>
        </div>
      </div>
      {#if flightView === '3d'}
        <FlightView3D
          history={$frameHistory}
          frame={$latestFrame}
          heading={$latestFrame?.heading_deg ?? 0}
          altFt={$latestFrame?.alt_ft ?? 0}
          iasKt={$latestFrame?.ias_kt ?? 0}
          pitchDeg={$latestFrame?.pitch_deg ?? 0}
          rollDeg={$latestFrame?.roll_deg ?? 0}
          failures={$latestFrame?.active_failures ?? []}
          environment={$latestFrame?.environment}
        />
      {:else}
        <FlightCanvas
          history={$frameHistory}
          heading={$latestFrame?.heading_deg ?? 0}
          altFt={$latestFrame?.alt_ft ?? 0}
          iasKt={$latestFrame?.ias_kt ?? 0}
          failures={$latestFrame?.active_failures ?? []}
        />
      {/if}
    </section>

    <section class="panel panel-perf">
      <div class="panel-head">
        <h2>Performance</h2>
      </div>
      <ScoreGauge score={$latestFrame?.pilot_score ?? 0} {band} />
      <ScoreHistory history={$frameHistory} />
      <div class="panel-head spaced">
        <h2>Scenario timeline</h2>
        <span class="hint">{$latestFrame?.scenario_events_pending ?? 0} pending</span>
      </div>
      <ScenarioTimeline
        events={$latestFrame?.timeline?.events ?? []}
        simTime={$latestFrame?.sim_time_s ?? 0}
      />
    </section>
  </div>

  <!-- Bottom row: log + overrides -->
  <div class="grid-bottom">
    <section class="panel panel-log">
      <div class="panel-head">
        <h2>Adaptation log</h2>
        <span class="hint">{($latestFrame?.adaptation_log ?? []).length} entries</span>
      </div>
      <AdaptationLog entries={$latestFrame?.adaptation_log ?? []} />
    </section>

    <section class="panel panel-actions">
      <div class="panel-head">
        <h2>Instructor overrides</h2>
      </div>
      <FailureOverridePanel />
    </section>
  </div>
</div>

<style>
  .dash {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    min-height: 0;
  }

  .panel {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    min-height: 0;
  }

  .panel-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .panel-head.spaced {
    margin-top: 16px;
    margin-bottom: 8px;
  }

  .panel-head h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
  }

  .view-toggle {
    display: flex;
    gap: 4px;
    padding: 2px;
    border-radius: var(--radius-sm);
    background: var(--bg-muted);
    border: 1px solid var(--border-subtle);
  }

  .view-toggle button {
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 6px;
  }

  .view-toggle button.active {
    background: var(--bg-surface);
    color: var(--text);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  }

  .kpi-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0;
    padding: 12px 20px;
    flex-shrink: 0;
  }

  .kpi {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 0 20px;
  }

  .kpi:first-child {
    padding-left: 4px;
  }

  .kpi-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .kpi-value {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }

  .kpi-value small {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
  }

  .kpi-value.band-excellent { color: #15803d; font-size: 16px; text-transform: capitalize; }
  .kpi-value.band-moderate { color: #1d4ed8; font-size: 16px; text-transform: capitalize; }
  .kpi-value.band-struggling { color: #c2410c; font-size: 16px; text-transform: capitalize; }

  .kpi-value.kpi-sm {
    font-size: 15px;
  }

  .kpi-divider {
    width: 1px;
    height: 32px;
    background: var(--border-subtle);
    flex-shrink: 0;
  }

  .grid-main {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .panel-flight,
  .panel-perf {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  .grid-bottom {
    display: grid;
    grid-template-columns: 1.35fr 0.65fr;
    gap: 12px;
    height: 118px;
    min-height: 118px;
    max-height: 118px;
    overflow: hidden;
  }

  .panel-log {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    padding-bottom: 10px;
  }

  .panel-log :global(.log) {
    flex: 1;
    min-height: 0;
  }

  .panel-actions {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 0;
    overflow: hidden;
  }

  .panel-actions .panel-head {
    margin-bottom: 10px;
  }

  .panel-perf {
    overflow-y: auto;
    overscroll-behavior: contain;
  }

  .panel-perf .panel-head.spaced {
    margin-top: 12px;
  }

  @media (max-width: 900px) {
    .grid-main,
    .grid-bottom {
      grid-template-columns: 1fr;
    }
    .grid-bottom {
      max-height: none;
    }
    .kpi-divider {
      display: none;
    }
    .kpi {
      padding: 8px 12px 8px 4px;
    }
  }
</style>
