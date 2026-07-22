<script setup>
import { computed, ref } from 'vue'
import { ask } from '../api'

const question = ref('')
const result = ref(null)
const error = ref(null)
const busy = ref(false)
const highlighted = ref(null)

async function submit() {
  error.value = null
  result.value = null
  highlighted.value = null
  busy.value = true
  try {
    result.value = await ask(question.value)
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
      <button type="submit" :disabled="busy" :aria-busy="busy">{{ $t('ask_submit') }}</button>
    </form>
    <p v-if="error">{{ error }}</p>
    <article v-if="result">
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
    </article>
  </section>
</template>

<style scoped>
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
