// vite.config.ts
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.UAV_BACKEND_URL || 'http://127.0.0.1:8002'
  const backendProxy = { target: backendTarget, changeOrigin: true, ws: true }

  return {
    plugins: [vue()],

    // 开发时所有模块共用一个后端；生产构建由后端同源提供。
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': backendProxy,
        '/ws': backendProxy,
        '/rose-pictures': backendProxy,
      }
    },

    // 子路径部署：构建时 VITE_BASE=/uav/ npm run build；默认根路径（原行为不变）
    base: env.VITE_BASE || '/',

    build: {
      target: 'es2015',
      sourcemap: false,
      assetsInlineLimit: 4096,
      rollupOptions: {
        output: {
          assetFileNames: (assetInfo) => {
            let extType = assetInfo.name?.split('.').at(1);
            if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType || '')) {
              extType = 'img';
            }
            return `assets/${extType}/[name]-[hash][extname]`;
          },
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          // Preserve lazy-module initialization order: leaflet.heat reads the
          // Leaflet global during import and must not run in an eager vendor chunk.
        }
      }
    }
  }
})
