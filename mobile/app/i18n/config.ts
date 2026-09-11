import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as SecureStore from 'expo-secure-store';
import { locales } from './locales';

const LANGUAGE_KEY = 'app_language';

// Initialize i18next
i18n
  .use(initReactI18next)
  .init({
    compatibilityJSON: 'v3', // For React Native compatibility
    fallbackLng: 'en',
    resources: locales,
    interpolation: {
      escapeValue: false,
    },
    defaultNS: 'translation',
    ns: ['translation'],
  });

// Load saved language preference
export const initializeLanguage = async () => {
  try {
    const savedLanguage = await SecureStore.getItemAsync(LANGUAGE_KEY);
    if (savedLanguage && Object.keys(locales).includes(savedLanguage)) {
      await i18n.changeLanguage(savedLanguage);
    }
  } catch (error) {
    console.warn('Failed to load language preference:', error);
  }
};

// Save language preference
export const setLanguagePreference = async (lang: string) => {
  try {
    await SecureStore.setItemAsync(LANGUAGE_KEY, lang);
    await i18n.changeLanguage(lang);
  } catch (error) {
    console.warn('Failed to save language preference:', error);
    await i18n.changeLanguage(lang);
  }
};

export default i18n;
