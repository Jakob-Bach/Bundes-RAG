import { ref, watch } from 'vue'

// Sortable columns of the status table; label is the i18n key of the header.
export const sortableColumns = [
  { key: 'file', label: 'status_th_file' },
  { key: 'kind', label: 'status_th_kind' },
  { key: 'status', label: 'status_th_status' },
  { key: 'title', label: 'status_th_title' },
  { key: 'dokumentnummer', label: 'status_th_dokumentnummer' },
  { key: 'datum', label: 'status_th_datum' },
  { key: 'pages', label: 'status_th_pages' },
  { key: 'chunks', label: 'status_th_chunks' },
  { key: 'doc_id', label: 'status_th_doc_id' },
]

const STORAGE_KEY = 'bundesrag.status_sort'

function loadStoredSort() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (
      sortableColumns.some((column) => column.key === parsed.key) &&
      typeof parsed.ascending === 'boolean'
    ) {
      return parsed
    }
  } catch {
    // Missing, unparseable, or blocked (storage disabled) — start unsorted.
  }
  return null
}

// Module-scope refs so the sort choice survives leaving and re-entering the
// status view (the component is destroyed on every tab switch).
const storedSort = loadStoredSort()
const sortKey = ref(storedSort ? storedSort.key : null)
const sortAscending = ref(storedSort ? storedSort.ascending : true)

watch([sortKey, sortAscending], ([key, ascending]) => {
  try {
    if (key === null) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ key, ascending }))
    }
  } catch {
    // Storage unavailable — sorting still works for the current page load.
  }
})

export function useStatusSort() {
  function toggleSort(key) {
    if (sortKey.value === key) {
      sortAscending.value = !sortAscending.value
    } else {
      sortKey.value = key
      sortAscending.value = true
    }
  }

  return { sortKey, sortAscending, toggleSort }
}
