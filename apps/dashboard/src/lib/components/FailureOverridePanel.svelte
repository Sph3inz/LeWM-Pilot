<script lang="ts">
  import { sendUpstream } from '$lib/stores/telemetry';

  const failures = [
    { id: 'engine_failure', label: 'Engine' },
    { id: 'attitude_failure', label: 'Attitude' },
    { id: 'comms_failure', label: 'Comms' },
    { id: 'hydraulic_leak', label: 'Hydraulic' }
  ];
</script>

<div class="row">
  {#each failures as f}
    <button
      class="btn btn-soft override-btn"
      type="button"
      onclick={() => sendUpstream({ type: 'manual_failure', failure_id: f.id })}
    >
      {f.label}
    </button>
  {/each}
</div>

<style>
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .override-btn {
    flex: 1;
    min-width: 0;
    padding: 6px 10px;
    font-size: 12px;
  }
</style>
