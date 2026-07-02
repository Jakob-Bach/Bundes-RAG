<template>
  <main class="container">
    <nav>
      <ul>
        <li><strong>Bundes-RAG</strong></li>
      </ul>
      <ul>
        <li><router-link to="/status">Status</router-link></li>
        <li><router-link to="/download">Herunterladen</router-link></li>
        <li><router-link to="/index">Indexieren</router-link></li>
        <li><router-link to="/ask">Fragen</router-link></li>
        <li><router-link to="/clear">Löschen</router-link></li>
      </ul>
    </nav>
    <router-view />
  </main>
</template>
