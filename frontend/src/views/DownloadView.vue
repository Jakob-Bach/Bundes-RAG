<script setup>
import { onUnmounted, ref } from 'vue'
import { cancelDownloadJob, getDownloadJob, respondToDownloadJob, startDownload } from '../api'
import UsageStats from '../components/UsageStats.vue'

const prompt = ref('')
const job = ref(null)
const error = ref(null)
const answerText = ref('')
const countValue = ref(0)
const cancelRequested = ref(false)
let timer = null

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function startPolling(id) {
  stopPolling()
  timer = setInterval(async () => {
    try {
      const next = await getDownloadJob(id)
      const wasWaiting = job.value && job.value.status === 'waiting_input'
      if (next.status === 'waiting_input' && next.pending.kind === 'confirm_count' && !wasWaiting) {
        countValue.value = next.pending.num_to_download
      }
      job.value = next
      if (['done', 'error', 'cancelled'].includes(next.status)) stopPolling()
    } catch (e) {
      error.value = e.message
      stopPolling()
    }
  }, 1500)
}

async function submit() {
  error.value = null
  cancelRequested.value = false
  try {
    job.value = await startDownload(prompt.value)
    startPolling(job.value.id)
  } catch (e) {
    error.value = e.message
  }
}

async function cancel() {
  error.value = null
  try {
    await cancelDownloadJob(job.value.id)
    cancelRequested.value = true
  } catch (e) {
    error.value = e.message
  }
}

async function respond(answer) {
  error.value = null
  try {
    await respondToDownloadJob(job.value.id, answer)
    answerText.value = ''
    // Show a busy state immediately instead of waiting for the next poll.
    job.value = { ...job.value, status: 'running', pending: null }
  } catch (e) {
    error.value = e.message
  }
}

onUnmounted(stopPolling)
</script>

<template>
  <section>
    <h2>{{ $t('download_title') }}</h2>
    <form @submit.prevent="submit">
      <label>
        {{ $t('download_prompt_label') }}
        <textarea
          v-model="prompt"
          rows="3"
          :placeholder="$t('download_prompt_placeholder')"
          required
        ></textarea>
      </label>
      <button type="submit" :disabled="job && (job.status === 'running' || job.status === 'waiting_input')">
        {{ $t('download_submit') }}
      </button>
    </form>
    <p v-if="error">{{ error }}</p>
    <template v-if="job">
      <p
        v-if="cancelRequested && (job.status === 'running' || job.status === 'waiting_input')"
        aria-busy="true"
      >
        {{ $t('cancel_requested') }}
      </p>
      <template v-else-if="job.status === 'running'">
        <p aria-busy="true">{{ $t('download_running') }}</p>
        <template v-if="job.progress && job.progress.total > 0">
          <progress :value="job.progress.current" :max="job.progress.total"></progress>
          <small>{{
            $t('progress_count', { current: job.progress.current, total: job.progress.total })
          }}</small>
        </template>
      </template>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'ask_user'">
        <p>{{ job.pending.question }}</p>
        <form @submit.prevent="respond(answerText)">
          <input v-model="answerText" type="text" required />
          <button type="submit">{{ $t('answer_submit') }}</button>
        </form>
      </article>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'confirm_filters'">
        <pre>{{ job.pending.filters_text }}</pre>
        <p>{{ $t('confirm_use_query') }}</p>
        <div class="grid">
          <button @click="respond('true')">{{ $t('yes') }}</button>
          <button class="secondary" @click="respond('false')">{{ $t('no') }}</button>
        </div>
      </article>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'confirm_count'">
        <p>{{
          $t('ask_download_count', {
            num_matched: job.pending.num_matched,
            num_existing: job.pending.num_existing,
            num_to_download: job.pending.num_to_download,
          })
        }}</p>
        <form @submit.prevent="respond(String(countValue))">
          <input
            v-model.number="countValue"
            type="number"
            min="0"
            :max="job.pending.num_to_download"
            required
          />
          <button type="submit">{{ $t('count_submit') }}</button>
        </form>
      </article>

      <template v-else-if="job.status === 'done'">
        <p>
          {{ $t('download_done', { num_documents: job.result.num_documents }) }}
          <template v-if="job.result.num_skipped">
            {{ $t('download_skipped_existing', { num_skipped: job.result.num_skipped }) }}
          </template>
          <template v-if="job.result.num_failed">
            {{ $t('download_partial_failure', { num_failed: job.result.num_failed }) }}
          </template>
        </p>
        <UsageStats :usage="job.result.usage" />
      </template>
      <p v-else-if="job.status === 'cancelled'">{{ $t('operation_cancelled') }}</p>
      <p v-else-if="job.status === 'error'">{{ $t('error_prefix', { error: job.error }) }}</p>

      <button
        v-if="(job.status === 'running' || job.status === 'waiting_input') && !cancelRequested"
        class="secondary"
        @click="cancel"
      >
        {{ $t('cancel_submit') }}
      </button>
    </template>
  </section>
</template>
