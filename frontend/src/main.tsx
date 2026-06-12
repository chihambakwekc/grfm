import React from "react"
import ReactDOM from "react-dom/client"
import { registerSW } from "virtual:pwa-register"
import "@fontsource-variable/geist"
import "./styles.css"
import "./i18n"
import { App } from "./App"

if (import.meta.env.PROD) {
  registerSW({ immediate: true })
} else if ("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations()
    .then((registrations) => Promise.all(registrations.map((registration) => registration.unregister())))
    .then(() => caches.keys())
    .then((cacheNames) => Promise.all(cacheNames.filter((name) => name.startsWith("grfm-") || name.includes("workbox")).map((name) => caches.delete(name))))
    .catch(() => undefined)
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
