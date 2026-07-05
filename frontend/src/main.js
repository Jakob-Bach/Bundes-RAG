import '@picocss/pico'
import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import { getConfig } from './api'
import App from './App.vue'
import de from './locales/de'
import en from './locales/en'
import router from './router'

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'de',
  fallbackLocale: 'de',
  messages: { de, en },
})

// The UI language is the server-side `language` setting (shared with the CLI),
// fetched once before mounting to avoid a flash of wrong-language UI.
async function bootstrap() {
  try {
    const { language } = await getConfig()
    if (i18n.global.availableLocales.includes(language)) {
      i18n.global.locale.value = language
      document.documentElement.lang = language
    }
  } catch {
    // Backend unreachable: keep the German default so the SPA still renders.
  }
  createApp(App).use(router).use(i18n).mount('#app')
}

bootstrap()
