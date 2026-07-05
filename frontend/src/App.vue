<template>
  <main class="container">
    <nav>
      <ul>
        <li><strong>Bundes-RAG</strong></li>
      </ul>
      <ul>
        <li><router-link to="/status">{{ $t('nav_status') }}</router-link></li>
        <li><router-link to="/download">{{ $t('nav_download') }}</router-link></li>
        <li><router-link to="/index">{{ $t('nav_index') }}</router-link></li>
        <li><router-link to="/ask">{{ $t('nav_ask') }}</router-link></li>
        <li><router-link to="/clear">{{ $t('nav_clear') }}</router-link></li>
      </ul>
    </nav>
    <router-view />
  </main>
</template>
