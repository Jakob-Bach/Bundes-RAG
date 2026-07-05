<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { clear } from '../api'

const { t } = useI18n()
const result = ref(null)
const error = ref(null)
const busy = ref(false)

async function submit() {
  if (!window.confirm(t('confirm_delete_all'))) {
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
    <h2>{{ $t('clear_title') }}</h2>
    <p>{{ $t('clear_description') }}</p>
    <button :disabled="busy" :aria-busy="busy" @click="submit">{{ $t('clear_submit') }}</button>
    <p v-if="error">{{ error }}</p>
    <p v-if="result">{{ $t('delete_done', { num_files: result.num_files }) }}</p>
  </section>
</template>
