<script setup>
import { ref } from 'vue'
import { clear } from '../api'

const result = ref(null)
const error = ref(null)
const busy = ref(false)

async function submit() {
  if (!window.confirm('Wirklich alle heruntergeladenen Dokumente und die Vektordatenbank löschen?')) {
    return
  }
  error.value = null
  result.value = null
  busy.value = true
  try {
    result.value = await clear(true)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section>
    <h2>Löschen</h2>
    <p>
      Löscht alle heruntergeladenen PDFs, setzt die Vektordatenbank zurück und leert die Liste
      wartender Dokumente. Dieser Schritt kann nicht rückgängig gemacht werden.
    </p>
    <button :disabled="busy" :aria-busy="busy" @click="submit">Alles löschen</button>
    <p v-if="error">{{ error }}</p>
    <p v-if="result">
      Fertig: {{ result.num_files }} Dateien gelöscht und Vektordatenbank zurückgesetzt.
    </p>
  </section>
</template>
