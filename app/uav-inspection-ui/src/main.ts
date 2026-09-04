import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router' // 引入路由实例

const app = createApp(App)

// 关键步骤：使用路由插件
app.use(router)

app.mount('#app')
