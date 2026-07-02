import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { createThemeProvider } from './shared/theme'

const app = createApp(App)
app.use(createPinia())
app.use(router)
createThemeProvider()
app.mount('#app')
