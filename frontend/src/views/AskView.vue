<script setup>
import { computed, ref, watch } from 'vue'
import { ask, askStats } from '../api'
import UsageStats from '../components/UsageStats.vue'

const question = ref('')
const filterKind = ref('')
const filterWahlperiode = ref('')
const filterDatumStart = ref('')
const filterDatumEnd = ref('')
const result = ref(null)
const error = ref(null)
const busy = ref(false)
const highlighted = ref(null)
// Ask stats (corpus size) for the current filters, shown before the user asks
// so they can judge how narrow their filter is. Refreshed whenever a filter
// changes. Distinct from the LLM usage stats shown after the answer.
const liveAskStats = ref(null)

// Only the filters the user actually set are sent; null means unfiltered
// retrieval (the backend treats an all-empty filters object the same way).
function buildFilters() {
  const filters = {}
  if (filterKind.value) filters.kind = filterKind.value
  if (filterWahlperiode.value) filters.wahlperiode = Number(filterWahlperiode.value)
  if (filterDatumStart.value) filters.datum_start = filterDatumStart.value
  if (filterDatumEnd.value) filters.datum_end = filterDatumEnd.value
  return Object.keys(filters).length ? filters : null
}

// A monotonic token drops results of ask-stats requests overtaken by a newer
// one (filters can change faster than the request round-trips).
let askStatsToken = 0
async function refreshAskStats() {
  const token = ++askStatsToken
  try {
    const stats = await askStats(buildFilters())
    if (token === askStatsToken) liveAskStats.value = stats
  } catch {
    if (token === askStatsToken) liveAskStats.value = null
  }
}

// Renders the ask-stats figures as {key, params} for $t; used both for the
// pre-ask hint (kind='hint') and the line prefacing an answer (kind='info').
function askStatsMessage(stats, kind) {
  if (!stats) return null
  const filtered = stats.num_filtered_documents != null
  return {
    key: filtered ? `ask_stats_${kind}_filtered` : `ask_stats_${kind}`,
    params: {
      num_documents: stats.num_documents,
      num_chunks: stats.num_chunks,
      top_k: stats.top_k,
      num_filtered_documents: stats.num_filtered_documents,
      num_filtered_chunks: stats.num_filtered_chunks,
    },
  }
}

const askStatsHint = computed(() => askStatsMessage(liveAskStats.value, 'hint'))
const answerAskStats = computed(() => askStatsMessage(result.value?.ask_stats, 'info'))

watch(
  [filterKind, filterWahlperiode, filterDatumStart, filterDatumEnd],
  refreshAskStats,
  { immediate: true },
)

async function submit() {
  error.value = null
  result.value = null
  highlighted.value = null
  busy.value = true
  try {
    result.value = await ask(question.value, buildFilters())
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

// Splits the answer text into plain-text segments and citation references.
// Matches [n] and [n, m] where every number is a valid source index; anything
// else (e.g. a bracketed year) stays plain text.
const answerParts = computed(() => {
  if (!result.value) return []
  const validIndexes = new Set(result.value.sources.map((s) => s.index))
  const text = result.value.answer_text
  const parts = []
  let last = 0
  for (const match of text.matchAll(/\[(\d+(?:\s*,\s*\d+)*)\]/g)) {
    const refs = match[1].split(',').map((n) => parseInt(n.trim(), 10))
    if (!refs.every((n) => validIndexes.has(n))) continue
    if (match.index > last) parts.push({ text: text.slice(last, match.index) })
    parts.push({ refs })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last) })
  return parts
})

function jumpToSource(index) {
  highlighted.value = index
  const el = document.getElementById(`source-${index}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    // Make sure the retrieved text is visible at the jump target.
    const details = el.querySelector('details')
    if (details) details.open = true
  }
}

function pdfLink(source) {
  if (!source.source_url) return null
  return source.page ? `${source.source_url}#page=${source.page}` : source.source_url
}
</script>

<template>
  <section>
    <h2>{{ $t('ask_title') }}</h2>
    <form @submit.prevent="submit">
      <label>
        {{ $t('ask_question_label') }}
        <textarea
          v-model="question"
          rows="3"
          :placeholder="$t('ask_placeholder')"
          required
        ></textarea>
      </label>
      <details class="filters">
        <summary>{{ $t('ask_filters_summary') }}</summary>
        <div class="grid">
          <label>
            {{ $t('ask_filter_kind') }}
            <select v-model="filterKind">
              <option value="">{{ $t('ask_filter_kind_all') }}</option>
              <option value="drucksache">{{ $t('kind_drucksache') }}</option>
              <option value="plenarprotokoll">{{ $t('kind_plenarprotokoll') }}</option>
            </select>
          </label>
          <label>
            {{ $t('ask_filter_wahlperiode') }}
            <input v-model="filterWahlperiode" type="number" min="1" step="1" />
          </label>
          <label>
            {{ $t('ask_filter_datum_start') }}
            <input v-model="filterDatumStart" type="date" />
          </label>
          <label>
            {{ $t('ask_filter_datum_end') }}
            <input v-model="filterDatumEnd" type="date" />
          </label>
        </div>
      </details>
      <p v-if="askStatsHint" class="ask-stats-hint">{{ $t(askStatsHint.key, askStatsHint.params) }}</p>
      <button type="submit" :disabled="busy" :aria-busy="busy">{{ $t('ask_submit') }}</button>
    </form>
    <p v-if="error">{{ error }}</p>
    <article v-if="result">
      <p v-if="answerAskStats" class="ask-stats-info">
        {{ $t(answerAskStats.key, answerAskStats.params) }}
      </p>
      <p class="answer">
        <template v-for="(part, i) in answerParts" :key="i">
          <span v-if="part.text">{{ part.text }}</span>
          <span v-else class="citation"
            >[<template v-for="(ref, j) in part.refs" :key="ref"
              ><template v-if="j > 0">, </template
              ><a href="#" @click.prevent="jumpToSource(ref)">{{ ref }}</a></template
            >]</span
          >
        </template>
      </p>
      <footer v-if="result.sources.length">
        <strong>{{ $t('sources_header') }}</strong>
        <ul class="sources">
          <li
            v-for="source in result.sources"
            :id="`source-${source.index}`"
            :key="source.index"
            :class="{ highlighted: highlighted === source.index }"
          >
            <span class="source-index">[{{ source.index }}]</span>
            <a
              v-if="pdfLink(source)"
              :href="pdfLink(source)"
              target="_blank"
              rel="noopener noreferrer"
              >{{ source.citation }}</a
            >
            <span v-else>{{ source.citation }}</span>
            <details>
              <summary>{{ $t('source_show_text') }}</summary>
              <blockquote class="source-text">{{ source.text }}</blockquote>
            </details>
          </li>
        </ul>
      </footer>
      <UsageStats :usage="result.usage" />
    </article>
  </section>
</template>

<style scoped>
.ask-stats-hint,
.ask-stats-info {
  color: var(--pico-muted-color, #6c757d);
  font-size: 0.875em;
}
.answer {
  white-space: pre-wrap;
}
.citation a {
  text-decoration: none;
  font-weight: bold;
}
.sources li {
  border-radius: 0.25rem;
  padding: 0.25rem 0.5rem;
  transition: background-color 0.5s;
}
.sources li.highlighted {
  background-color: var(--pico-mark-background-color, #ffdd57);
}
.source-index {
  font-weight: bold;
  margin-right: 0.25rem;
}
.sources details {
  margin: 0.25rem 0 0;
}
.sources summary {
  font-size: 0.875em;
  cursor: pointer;
}
.source-text {
  white-space: pre-wrap;
  font-size: 0.875em;
  margin: 0.5rem 0 0;
}
</style>
