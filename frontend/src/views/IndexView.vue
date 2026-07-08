<script setup>
import { onUnmounted, ref } from 'vue'
import { cancelIndexJob, getIndexJob, startIndex } from '../api'

const job = ref(null)
const error = ref(null)
const cancelRequested = ref(false)
let timer = null

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function submit() {
  error.value = null
  cancelRequested.value = false
  try {
    job.value = await startIndex()
  } catch (e) {
    error.value = e.message
    return
  }
  stopPolling()
  timer = setInterval(async () => {
    try {
      job.value = await getIndexJob(job.value.id)
      if (['done', 'error', 'cancelled'].includes(job.value.status)) stopPolling()
    } catch (e) {
      error.value = e.message
      stopPolling()
    }
  }, 1500)
}

async function cancel() {
  error.value = null
  try {
    await cancelIndexJob(job.value.id)
    cancelRequested.value = true
  } catch (e) {
    error.value = e.message
  }
}

onUnmounted(stopPolling)
</script>

<template>
  <section>
    <h2>{{ $t('index_title') }}</h2>
    <p>{{ $t('index_description') }}</p>
    <button :disabled="job && job.status === 'running'" @click="submit">
      {{ $t('index_submit') }}
    </button>
    <p v-if="error">{{ error }}</p>
    <template v-if="job">
      <p v-if="cancelRequested && job.status === 'running'" aria-busy="true">
        {{ $t('cancel_requested') }}
      </p>
      <template v-else-if="job.status === 'running'">
        <p aria-busy="true">{{ $t('index_running') }}</p>
        <p v-if="job.counts">
          {{
            $t('index_counts', {
              num_to_index: job.counts.num_to_index,
              num_indexed: job.counts.num_indexed,
            })
          }}
        </p>
        <template v-if="job.progress && job.progress.total > 0">
          <progress :value="job.progress.current" :max="job.progress.total"></progress>
          <small>{{
            $t('progress_count', { current: job.progress.current, total: job.progress.total })
          }}</small>
        </template>
      </template>
      <p v-else-if="job.status === 'done'">
        {{
          $t('index_done', {
            num_documents: job.result.num_documents,
            num_chunks: job.result.num_chunks,
          })
        }}
      </p>
      <p v-else-if="job.status === 'cancelled'">{{ $t('operation_cancelled') }}</p>
      <p v-else-if="job.status === 'error'">{{ $t('error_prefix', { error: job.error }) }}</p>

      <button
        v-if="job.status === 'running' && !cancelRequested"
        class="secondary"
        @click="cancel"
      >
        {{ $t('cancel_submit') }}
      </button>
    </template>
  </section>
</template>
