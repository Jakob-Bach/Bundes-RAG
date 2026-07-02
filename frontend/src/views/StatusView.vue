<script setup>
import { onMounted, ref } from 'vue'
import { getStatus } from '../api'

const status = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    status.value = await getStatus()
  } catch (e) {
    error.value = e.message
  }
})

function fileName(path) {
  return path.split(/[\\/]/).pop()
}
</script>

<template>
  <section>
    <h2>Status</h2>
    <p v-if="error">{{ error }}</p>
    <p v-else-if="!status" aria-busy="true">Lade Status …</p>
    <template v-else>
      <p>
        Heruntergeladen: {{ status.num_downloaded }}<br />
        Indexiert: {{ status.num_indexed }}
      </p>
      <table v-if="status.files.length">
        <thead>
          <tr>
            <th>Datei</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in status.files" :key="file.pdf_path">
            <td>{{ fileName(file.pdf_path) }}</td>
            <td>{{ file.indexed ? 'indexiert' : 'nicht indexiert' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else>Keine Dokumente heruntergeladen.</p>
    </template>
  </section>
</template>
