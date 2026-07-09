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

function formatSize(numBytes) {
  let value = numBytes
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unit = units[0]
  for (const candidate of units) {
    unit = candidate
    if (value < 1024 || candidate === 'TB') break
    value /= 1024
  }
  return unit === 'B' ? `${value} B` : `${value.toFixed(1)} ${unit}`
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
        {{ $t('status_num_indexed', { count: status.num_indexed }) }}<br />
        {{ $t('status_num_chunks', { count: status.num_chunks }) }}<br />
        {{ $t('status_pdf_size', { size: formatSize(status.pdf_size_bytes) }) }}<br />
        {{ $t('status_vectorstore_size', { size: formatSize(status.vectorstore_size_bytes) }) }}
      </p>
      <div v-if="status.files.length" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ $t('status_th_file') }}</th>
              <th>{{ $t('status_th_kind') }}</th>
              <th>{{ $t('status_th_status') }}</th>
              <th>{{ $t('status_th_title') }}</th>
              <th>{{ $t('status_th_dokumentnummer') }}</th>
              <th>{{ $t('status_th_datum') }}</th>
              <th>{{ $t('status_th_pages') }}</th>
              <th>{{ $t('status_th_chunks') }}</th>
              <th>{{ $t('status_th_doc_id') }}</th>
              <th>{{ $t('status_th_source') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in status.files" :key="file.pdf_path">
              <td>{{ fileName(file.pdf_path) }}</td>
              <td>{{ file.kind ? $t('kind_' + file.kind) : '–' }}</td>
              <td>
                {{ file.indexed ? $t('status_file_indexed') : $t('status_file_not_indexed') }}
              </td>
              <td>{{ file.info?.citation_label ?? '–' }}</td>
              <td>{{ file.info?.dokumentnummer ?? '–' }}</td>
              <td>{{ file.info?.datum ?? '–' }}</td>
              <td>{{ file.info?.num_pages ?? '–' }}</td>
              <td>{{ file.info?.num_chunks ?? '–' }}</td>
              <td>{{ file.info?.doc_id ?? '–' }}</td>
              <td>
                <a
                  v-if="file.info?.source_url"
                  :href="file.info.source_url"
                  target="_blank"
                  rel="noopener"
                >
                  {{ $t('status_source_link') }}
                </a>
                <template v-else>–</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else>{{ $t('status_no_documents') }}</p>
    </template>
  </section>
</template>

<style scoped>
.table-scroll {
  overflow-x: auto;
}
</style>
