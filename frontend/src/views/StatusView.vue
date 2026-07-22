<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteFile, getStatus } from '../api'
import { sortableColumns, useStatusSort } from '../statusSort'

const { t } = useI18n()
const status = ref(null)
const error = ref(null)
// pdf_path of the file whose deletion is in flight; null when idle.
const deleting = ref(null)

const { sortKey, sortAscending, toggleSort } = useStatusSort()

// One rendered line per operation kind with recorded Mistral usage, in the
// backend's canonical order; the cost suffix is omitted when the backend
// sent no cost estimate (price settings unset).
const usageLines = computed(() => {
  const totals = status.value?.usage_totals ?? {}
  return ['download', 'index', 'ask']
    .filter((operation) => totals[operation])
    .map((operation) => {
      const usage = totals[operation]
      let line = t('usage_totals_line', {
        operation: t('usage_op_' + operation),
        tokens: usage.total_tokens,
        num_operations: usage.num_operations,
        seconds: usage.llm_seconds.toFixed(1),
      })
      if (usage.cost != null) {
        line += t('usage_cost_suffix', { cost: usage.cost.toFixed(4), currency: usage.currency })
      }
      return line
    })
})

function sortValue(file, key) {
  switch (key) {
    case 'file':
      return fileName(file.pdf_path)
    case 'kind':
      return file.kind ? t('kind_' + file.kind) : null
    case 'status':
      return file.indexed ? 1 : 0
    case 'title':
      return file.info?.citation_label
    case 'dokumentnummer':
      return file.info?.dokumentnummer
    case 'datum':
      return file.info?.datum
    case 'pages':
      return file.info?.num_pages
    case 'chunks':
      return file.info?.num_chunks
    case 'doc_id':
      return file.info?.doc_id
    default:
      return null
  }
}

const sortedFiles = computed(() => {
  const files = status.value?.files ?? []
  if (!sortKey.value) return files
  const direction = sortAscending.value ? 1 : -1
  return [...files].sort((a, b) => {
    const va = sortValue(a, sortKey.value)
    const vb = sortValue(b, sortKey.value)
    // Files without a value for the column always sort last.
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    const cmp =
      typeof va === 'number' && typeof vb === 'number'
        ? va - vb
        : // numeric collation so e.g. Dokumentnummer 21/9 sorts before 21/10
          String(va).localeCompare(String(vb), undefined, { numeric: true })
    return cmp * direction
  })
})

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
      <p v-if="usageLines.length">
        <strong>{{ $t('usage_totals_header') }}</strong
        ><br />
        <template v-for="(line, i) in usageLines" :key="i">{{ line }}<br /></template>
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
              <th
                v-for="column in sortableColumns"
                :key="column.key"
                :aria-sort="
                  sortKey === column.key ? (sortAscending ? 'ascending' : 'descending') : null
                "
              >
                <button type="button" class="sort-button" @click="toggleSort(column.key)">
                  {{ $t(column.label)
                  }}<span class="sort-indicator" aria-hidden="true">{{
                    sortKey === column.key ? (sortAscending ? ' ▲' : ' ▼') : ''
                  }}</span>
                </button>
              </th>
              <th>{{ $t('status_th_source') }}</th>
              <th>{{ $t('status_th_actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in sortedFiles" :key="file.pdf_path">
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

/* Strip Pico's button styling so sortable headers look like plain header text. */
.sort-button {
  width: auto;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  box-shadow: none;
  color: inherit;
  font: inherit;
  text-align: inherit;
  white-space: nowrap;
  cursor: pointer;
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
