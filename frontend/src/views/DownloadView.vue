<script setup>
import { onUnmounted, ref } from 'vue'
import { getDownloadJob, respondToDownloadJob, startDownload } from '../api'

const prompt = ref('')
const job = ref(null)
const error = ref(null)
const answerText = ref('')
const countValue = ref(0)
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
        countValue.value = next.pending.count
      }
      job.value = next
      if (next.status === 'done' || next.status === 'error') stopPolling()
    } catch (e) {
      error.value = e.message
      stopPolling()
    }
  }, 1500)
}

async function submit() {
  error.value = null
  try {
    job.value = await startDownload(prompt.value)
    startPolling(job.value.id)
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
    <h2>Herunterladen</h2>
    <form @submit.prevent="submit">
      <label>
        Beschreibung der gewünschten Dokumente
        <textarea
          v-model="prompt"
          rows="3"
          placeholder="Plenarprotokolle der 21. Wahlperiode."
          required
        ></textarea>
      </label>
      <button type="submit" :disabled="job && (job.status === 'running' || job.status === 'waiting_input')">
        Herunterladen starten
      </button>
    </form>
    <p v-if="error">{{ error }}</p>
    <template v-if="job">
      <p v-if="job.status === 'running'" aria-busy="true">Verarbeitung läuft …</p>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'ask_user'">
        <p>{{ job.pending.question }}</p>
        <form @submit.prevent="respond(answerText)">
          <input v-model="answerText" type="text" required />
          <button type="submit">Antworten</button>
        </form>
      </article>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'confirm_filters'">
        <pre>{{ job.pending.filters_text }}</pre>
        <p>Abfrage so verwenden?</p>
        <div class="grid">
          <button @click="respond('true')">Ja</button>
          <button class="secondary" @click="respond('false')">Nein</button>
        </div>
      </article>

      <article v-else-if="job.status === 'waiting_input' && job.pending.kind === 'confirm_count'">
        <p>
          {{ job.pending.count }} Dokumente gefunden. Wie viele sollen heruntergeladen werden
          (die neuesten zuerst, 0 zum Abbrechen)?
        </p>
        <form @submit.prevent="respond(String(countValue))">
          <input v-model.number="countValue" type="number" min="0" :max="job.pending.count" required />
          <button type="submit">Bestätigen</button>
        </form>
      </article>

      <p v-else-if="job.status === 'done'">
        Fertig: {{ job.result.num_documents }} Dokumente heruntergeladen.
        <template v-if="job.result.num_failed">
          Achtung: {{ job.result.num_failed }} Dokument(e) konnten nicht heruntergeladen werden
          und wurden übersprungen.
        </template>
      </p>
      <p v-else-if="job.status === 'error'">Fehler: {{ job.error }}</p>
    </template>
  </section>
</template>
