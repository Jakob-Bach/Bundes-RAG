import { createRouter, createWebHashHistory } from 'vue-router'
import AskView from './views/AskView.vue'
import ClearView from './views/ClearView.vue'
import DownloadView from './views/DownloadView.vue'
import IndexView from './views/IndexView.vue'
import StatusView from './views/StatusView.vue'

// Hash-based history so a hard page refresh always resolves against the
// StaticFiles mount without needing a server-side SPA fallback route.
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/status' },
    { path: '/status', component: StatusView },
    { path: '/download', component: DownloadView },
    { path: '/index', component: IndexView },
    { path: '/ask', component: AskView },
    { path: '/clear', component: ClearView },
  ],
})
