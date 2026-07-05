<script setup>
import { ref } from 'vue'
import { ask } from '../api'

const question = ref('')
const result = ref(null)
const error = ref(null)
const busy = ref(false)

async function submit() {
  error.value = null
  result.value = null
  busy.value = true
  try {
    result.value = await ask(question.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
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
      <p style="white-space: pre-wrap">{{ result.answer_text }}</p>
      <footer v-if="result.sources.length">
        <strong>{{ $t('sources_header') }}</strong>
        <ul>
          <li v-for="source in result.sources" :key="source">{{ source }}</li>
        </ul>
      </footer>
    </article>
  </section>
</template>
