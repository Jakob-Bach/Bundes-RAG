<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteFile, getStatus } from '../api'

const { t } = useI18n()
const status = ref(null)
const error = ref(null)
// pdf_path of the file whose deletion is in flight; null when idle.
const deleting = ref(null)

async function refresh() {
  try {
    status.value = await getStatus()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(refresh)

async function removeFile(file) {
  if (!window.confirm(t('confirm_delete_file', { file: fileName(file.pdf_path) }))) {
    return
  }
  error.value = null
  deleting.value = file.pdf_path
  try {
    await deleteFile(file.pdf_path)
    await refresh()
  } catch (e) {
    error.value = e.message
  } finally {
    deleting.value = null
  }
}

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
    <p v-if="!status && !error" aria-busy="true">{{ $t('status_loading') }}</p>
    <template v-if="status">
      <p>
        {{ $t('status_num_downloaded', { count: status.num_downloaded }) }}<br />
        {{ $t('status_num_indexed', { count: status.num_indexed }) }}<br />
        {{ $t('status_num_chunks', { count: status.num_chunks }) }}<br />
        {{ $t('status_pdf_size', { size: formatSize(status.pdf_size_bytes) }) }}<br />
        {{ $t('status_vectorstore_size', { size: formatSize(status.vectorstore_size_bytes) }) }}
      </p>
      <p v-if="status.num_chunks !== status.num_manifest_chunks">
        <strong>{{
          $t('status_chunk_mismatch', {
            num_chunks: status.num_chunks,
            num_expected: status.num_manifest_chunks,
          })
        }}</strong>
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
              <th>{{ $t('status_th_actions') }}</th>
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
              <td>
                <button
                  class="icon-button"
                  :aria-label="$t('delete_file_label')"
                  :title="$t('delete_file_label')"
                  :disabled="deleting !== null"
                  :aria-busy="deleting === file.pdf_path"
                  @click="removeFile(file)"
                >
                  <svg
                    v-if="deleting !== file.pdf_path"
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                  </svg>
                </button>
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

/* Compact icon-only variant of Pico's default (full-width, padded) button. */
.icon-button {
  width: auto;
  margin-bottom: 0;
  padding: 0.25rem 0.5rem;
  line-height: 1;
}

.icon-button svg {
  display: block;
}
</style>
