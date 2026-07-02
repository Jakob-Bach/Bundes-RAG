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
    <h2>Indexieren</h2>
    <p>
      Zerlegt alle heruntergeladenen, noch nicht indexierten Dokumente in Textabschnitte und
      speichert sie in der Vektordatenbank. Das kann je nach Umfang einige Zeit dauern.
    </p>
    <button :disabled="job && job.status === 'running'" @click="submit">Indexieren starten</button>
    <p v-if="error">{{ error }}</p>
    <template v-if="job">
      <p v-if="job.status === 'running'" aria-busy="true">Indexierung läuft …</p>
      <p v-else-if="job.status === 'done'">
        Fertig: {{ job.result.num_documents }} Dokumente, {{ job.result.num_chunks }}
        Textabschnitte gespeichert.
      </p>
      <p v-else-if="job.status === 'error'">Fehler: {{ job.error }}</p>
    </template>
  </section>
</template>
