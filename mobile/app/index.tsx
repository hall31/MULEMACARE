import React, { useEffect, useState } from 'react';
import { View, StyleSheet, useColorScheme } from 'react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { I18nextProvider } from 'react-i18next';
import i18n, { initializeLanguage } from './i18n/config';
import { MCareOnboarding } from './screens/MCareOnboarding';
import { MCareChat } from './screens/MCareChat';
import { MCareHistory } from './screens/MCareHistory';
import { mcareAPI } from './services/mcare';
import { ConversationResponse } from './services/mcare';
import * as SecureStore from 'expo-secure-store';

type Screen = 'onboarding' | 'chat' | 'history';

interface AppState {
  cssaId: string | null;
  beneficiaryName?: string;
  token: string | null;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
    mutations: {
      retry: 1,
    },
  },
});

export default function App() {
  const isDark = useColorScheme() === 'dark';
  const [isReady, setIsReady] = useState(false);
  const [currentScreen, setCurrentScreen] = useState<Screen>('onboarding');
  const [appState, setAppState] = useState<AppState>({
    cssaId: null,
    token: null,
  });

  useEffect(() => {
    const initialize = async () => {
      try {
        // Initialize i18n
        await initializeLanguage();

        // Load stored session
        const storedCssaId = await SecureStore.getItemAsync('cssa_id');
        const storedToken = await SecureStore.getItemAsync('mcare_token');
        const storedBeneficiary = await SecureStore.getItemAsync('beneficiary_name');

        if (storedCssaId && storedToken) {
          setAppState({
            cssaId: storedCssaId,
            beneficiaryName: storedBeneficiary || undefined,
            token: storedToken,
          });
          mcareAPI.setAuth(storedToken);
          setCurrentScreen('chat');
        }

        setIsReady(true);
      } catch (error) {
        console.warn('Initialization error:', error);
        setIsReady(true);
      }
    };

    initialize();
  }, []);

  const handleOnboardingComplete = async (cssaId: string, beneficiaryName?: string) => {
    try {
      // Generate a mock token (in production, this would come from auth endpoint)
      const mockToken = `token_${cssaId}_${Date.now()}`;

      // Store session
      await SecureStore.setItemAsync('cssa_id', cssaId);
      await SecureStore.setItemAsync('mcare_token', mockToken);
      if (beneficiaryName) {
        await SecureStore.setItemAsync('beneficiary_name', beneficiaryName);
      }

      mcareAPI.setAuth(mockToken);

      setAppState({
        cssaId,
        beneficiaryName,
        token: mockToken,
      });

      setCurrentScreen('chat');
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
    }
  };

  const handleBackToChat = () => {
    setCurrentScreen('chat');
  };

  const handleLogout = async () => {
    try {
      await SecureStore.deleteItemAsync('cssa_id');
      await SecureStore.deleteItemAsync('mcare_token');
      await SecureStore.deleteItemAsync('beneficiary_name');

      mcareAPI.clearAuth();

      setAppState({
        cssaId: null,
        token: null,
      });

      setCurrentScreen('onboarding');
    } catch (error) {
      console.warn('Logout error:', error);
    }
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: isDark ? '#111827' : '#fff',
    },
  });

  if (!isReady) {
    return (
      <View
        style={[
          styles.container,
          {
            justifyContent: 'center',
            alignItems: 'center',
          },
        ]}
      />
    );
  }

  return (
    <GestureHandlerRootView style={styles.container}>
      <SafeAreaProvider>
        <I18nextProvider i18n={i18n}>
          <QueryClientProvider client={queryClient}>
            {currentScreen === 'onboarding' && !appState.cssaId ? (
              <MCareOnboarding onComplete={handleOnboardingComplete} />
            ) : currentScreen === 'history' ? (
              <MCareHistory
                cssaId={appState.cssaId!}
                onSelectConversation={(conv) => {
                  // Handle conversation selection if needed
                  setCurrentScreen('chat');
                }}
                onBack={handleBackToChat}
              />
            ) : appState.cssaId ? (
              <MCareChat
                cssaId={appState.cssaId}
                beneficiaryName={appState.beneficiaryName}
                onBack={handleLogout}
              />
            ) : (
              <MCareOnboarding onComplete={handleOnboardingComplete} />
            )}
          </QueryClientProvider>
        </I18nextProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
