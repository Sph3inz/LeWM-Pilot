<script lang="ts">
  import { connectionState } from '$lib/stores/telemetry';
</script>

<span class="badge {$connectionState}">
  <span class="badge-dot"></span>
  {$connectionState}
</span>
