import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // Mismo "sitio" que el navegador (localhost vs 127.0.0.1) para que la cookie
      // de sesión de Flask se guarde y se envíe al usar http://localhost:5173
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes) => {
            const raw = proxyRes.headers['set-cookie']
            if (!raw) return
            proxyRes.headers['set-cookie'] = raw.map((c) =>
              c.replace(/;\s*Domain=[^;]*/gi, '')
            )
          })
        },
      },
    },
  },
  preview: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyRes', (proxyRes) => {
            const raw = proxyRes.headers['set-cookie']
            if (!raw) return
            proxyRes.headers['set-cookie'] = raw.map((c) =>
              c.replace(/;\s*Domain=[^;]*/gi, '')
            )
          })
        },
      },
    },
  },
})
