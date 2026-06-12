import i18n from "i18next"
import { initReactI18next } from "react-i18next"
import en from "./locales/en.json"
import nd from "./locales/nd.json"
import sn from "./locales/sn.json"

export const LANGUAGE_STORAGE_KEY = "grm.public.language"

export const supportedLanguages = [
  { code: "en", labelKey: "language.english" },
  { code: "sn", labelKey: "language.shona" },
  { code: "nd", labelKey: "language.ndebele" },
] as const

export type SupportedLanguage = typeof supportedLanguages[number]["code"]

function initialLanguage() {
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  return supportedLanguages.some((language) => language.code === stored) ? stored as SupportedLanguage : "en"
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      sn: { translation: sn },
      nd: { translation: nd },
    },
    lng: initialLanguage(),
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
    returnEmptyString: false,
  })

i18n.on("languageChanged", (language) => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
})

export default i18n
