<script setup>
import { onUnmounted, ref } from 'vue'
import { getIndexJob, startIndex } from '../api'

const job = ref(null)
const error = ref(null)
let timer = null

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function submit() {
  error.value = null
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
      if (job.value.status === 'done' || job.value.status === 'error') stopPolling()
    } catch (e) {
      error.value = e.message
      stopPolling()
    }
  }, 1500)
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
      <p v-if="job.status === 'running'" aria-busy="true">{{ $t('index_running') }}</p>
      <p v-else-if="job.status === 'done'">
        {{
          $t('index_done', {
            num_documents: job.result.num_documents,
            num_chunks: job.result.num_chunks,
          })
        }}
      </p>
      <p v-else-if="job.status === 'error'">{{ $t('error_prefix', { error: job.error }) }}</p>
    </template>
  </section>
</template>
