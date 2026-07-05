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
    <h2>{{ $t('status_title') }}</h2>
    <p v-if="error">{{ error }}</p>
    <p v-else-if="!status" aria-busy="true">{{ $t('status_loading') }}</p>
    <template v-else>
      <p>
        {{ $t('status_num_downloaded', { count: status.num_downloaded }) }}<br />
        {{ $t('status_num_indexed', { count: status.num_indexed }) }}
      </p>
      <table v-if="status.files.length">
        <thead>
          <tr>
            <th>{{ $t('status_th_file') }}</th>
            <th>{{ $t('status_th_status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in status.files" :key="file.pdf_path">
            <td>{{ fileName(file.pdf_path) }}</td>
            <td>{{ file.indexed ? $t('status_file_indexed') : $t('status_file_not_indexed') }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else>{{ $t('status_no_documents') }}</p>
    </template>
  </section>
</template>
