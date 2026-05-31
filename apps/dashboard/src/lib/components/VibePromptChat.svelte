<script lang="ts">
  import { sendUpstream } from '$lib/stores/telemetry';

  let prompt = $state('');

  function submit() {
    if (!prompt.trim()) return;
    sendUpstream({ type: 'vibe_prompt', text: prompt.trim() });
    prompt = '';
  }
</script>

<div class="composer">
  <button class="attach btn btn-ghost btn-icon" type="button" aria-label="Attach">+</button>
  <input
    bind:value={prompt}
    placeholder="Describe a training scenario…"
    onkeydown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
  />
  <button class="send btn btn-primary btn-icon" type="button" aria-label="Send" onclick={submit}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
  </button>
</div>

<style>
  .composer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-composer);
  }

  input {
    flex: 1;
    border: none;
    outline: none;
    background: transparent;
    font-size: 14px;
    color: var(--text);
    min-width: 0;
  }

  input::placeholder {
    color: var(--text-muted);
  }

  .attach {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .send {
    width: 34px;
    height: 34px;
    flex-shrink: 0;
  }
</style>
