<script setup>
// Mistral usage block of one finished operation (ask/download/index); the
// backend omits `usage` entirely when the operation made no API call, and
// leaves `cost` null when a price setting is unset.
defineProps({ usage: { type: Object, default: null } })
</script>

<template>
  <small v-if="usage" class="usage">
    <strong>{{ $t('usage_header') }}</strong><br />
    <template v-if="usage.chat_calls">
      {{
        $t('usage_chat', {
          input_tokens: usage.chat_input_tokens,
          output_tokens: usage.chat_output_tokens,
          num_calls: usage.chat_calls,
        })
      }}<br />
    </template>
    <template v-if="usage.embedding_calls">
      {{ $t('usage_embedding', { tokens: usage.embedding_tokens, num_calls: usage.embedding_calls })
      }}<br />
    </template>
    {{ $t('usage_time', { seconds: usage.llm_seconds.toFixed(1) }) }}<br />
    <template v-if="usage.cost != null">
      {{ $t('usage_cost', { cost: usage.cost.toFixed(4), currency: usage.currency }) }}
    </template>
  </small>
</template>

<style scoped>
.usage {
  display: block;
  margin-top: 0.5rem;
  color: var(--pico-muted-color, #6c757d);
}
</style>
