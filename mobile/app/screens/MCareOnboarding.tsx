import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ScrollView,
  useColorScheme,
  TextInput,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { mcareAPI } from '../services/mcare';
import { useTranslation } from 'react-i18next';

interface OnboardingProps {
  onComplete: (cssaId: string, beneficiaryName?: string) => void;
}

export const MCareOnboarding: React.FC<OnboardingProps> = ({ onComplete }) => {
  const { t, i18n } = useTranslation();
  const isDark = useColorScheme() === 'dark';
  const [step, setStep] = useState<'language' | 'member' | 'consent'>(
    'language'
  );
  const [cssaId, setCssaId] = useState('');
  const [beneficiaryName, setBeneficiaryName] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState(i18n.language as any);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['mcare-status'],
    queryFn: () => mcareAPI.getStatus(),
    staleTime: 5 * 60 * 1000,
  });

  const handleLanguageSelect = (lang: 'en' | 'fr' | 'sw') => {
    setSelectedLanguage(lang);
    i18n.changeLanguage(lang);
    mcareAPI.setLanguage(lang);
    setStep('member');
  };

  const handleVerifyMember = async () => {
    if (!cssaId.trim()) {
      setError(t('cssaIdRequired'));
      return;
    }

    setIsVerifying(true);
    setError(null);

    try {
      await mcareAPI.getStatus();
      setStep('consent');
    } catch (err: any) {
      setError(err.message || t('verificationFailed'));
    } finally {
      setIsVerifying(false);
    }
  };

  const handleConsent = () => {
    if (!cssaId.trim()) {
      setError(t('cssaIdRequired'));
      return;
    }
    onComplete(cssaId.toUpperCase(), beneficiaryName || undefined);
  };

  const handleGoBack = () => {
    if (step === 'member') {
      setStep('language');
      setError(null);
    } else if (step === 'consent') {
      setStep('member');
      setError(null);
    }
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: isDark ? '#111827' : '#fff',
    },
    content: {
      flex: 1,
      paddingHorizontal: 20,
      justifyContent: 'center',
    },
    logo: {
      fontSize: 36,
      textAlign: 'center',
      marginBottom: 20,
    },
    title: {
      fontSize: 24,
      fontWeight: '700',
      color: isDark ? '#f3f4f6' : '#1f2937',
      textAlign: 'center',
      marginBottom: 12,
    },
    subtitle: {
      fontSize: 14,
      color: isDark ? '#9ca3af' : '#6b7280',
      textAlign: 'center',
      lineHeight: 20,
      marginBottom: 32,
    },
    optionContainer: {
      gap: 12,
      marginBottom: 24,
    },
    optionButton: {
      paddingVertical: 16,
      paddingHorizontal: 20,
      borderRadius: 12,
      borderWidth: 2,
      borderColor: isDark ? '#374151' : '#e5e7eb',
      backgroundColor: 'transparent',
      justifyContent: 'center',
      alignItems: 'center',
    },
    optionButtonActive: {
      borderColor: '#3b82f6',
      backgroundColor: isDark ? '#1e3a8a' : '#eff6ff',
    },
    optionButtonText: {
      fontSize: 16,
      fontWeight: '600',
      color: isDark ? '#d1d5db' : '#374151',
    },
    optionButtonTextActive: {
      color: '#3b82f6',
    },
    input: {
      backgroundColor: isDark ? '#1f2937' : '#f9fafb',
      borderWidth: 1,
      borderColor: isDark ? '#374151' : '#e5e7eb',
      borderRadius: 8,
      paddingHorizontal: 16,
      paddingVertical: 12,
      marginBottom: 12,
      color: isDark ? '#f3f4f6' : '#1f2937',
      fontSize: 14,
    },
    inputLabel: {
      fontSize: 13,
      fontWeight: '600',
      color: isDark ? '#d1d5db' : '#374151',
      marginBottom: 8,
    },
    inputGroup: {
      marginBottom: 20,
    },
    errorText: {
      color: '#ef4444',
      fontSize: 12,
      marginBottom: 12,
      marginTop: -8,
    },
    consentBox: {
      backgroundColor: isDark ? '#1f2937' : '#f9fafb',
      borderLeftWidth: 4,
      borderLeftColor: '#f59e0b',
      padding: 16,
      borderRadius: 8,
      marginBottom: 24,
    },
    consentTitle: {
      fontSize: 14,
      fontWeight: '600',
      color: isDark ? '#d1d5db' : '#374151',
      marginBottom: 8,
    },
    consentText: {
      fontSize: 13,
      color: isDark ? '#9ca3af' : '#6b7280',
      lineHeight: 20,
      marginBottom: 8,
    },
    warningBox: {
      backgroundColor: isDark ? '#7f1d1d' : '#fee2e2',
      borderLeftWidth: 4,
      borderLeftColor: '#ef4444',
      padding: 12,
      borderRadius: 8,
      marginBottom: 24,
    },
    warningTitle: {
      fontSize: 13,
      fontWeight: '600',
      color: isDark ? '#fca5a5' : '#991b1b',
      marginBottom: 4,
    },
    warningText: {
      fontSize: 12,
      color: isDark ? '#fca5a5' : '#991b1b',
      lineHeight: 18,
    },
    buttonContainer: {
      gap: 12,
    },
    button: {
      paddingVertical: 14,
      paddingHorizontal: 20,
      borderRadius: 8,
      justifyContent: 'center',
      alignItems: 'center',
      flexDirection: 'row',
      gap: 8,
    },
    primaryButton: {
      backgroundColor: '#3b82f6',
    },
    primaryButtonText: {
      fontSize: 14,
      fontWeight: '600',
      color: '#fff',
    },
    secondaryButton: {
      backgroundColor: isDark ? '#374151' : '#e5e7eb',
    },
    secondaryButtonText: {
      fontSize: 14,
      fontWeight: '600',
      color: isDark ? '#f3f4f6' : '#1f2937',
    },
    disabledButton: {
      opacity: 0.5,
    },
    header: {
      paddingTop: 12,
      paddingHorizontal: 20,
      paddingBottom: 8,
      borderBottomWidth: 1,
      borderBottomColor: isDark ? '#374151' : '#e5e7eb',
      flexDirection: 'row',
      alignItems: 'center',
    },
    backButton: {
      paddingHorizontal: 12,
      paddingVertical: 6,
    },
    backButtonText: {
      fontSize: 16,
      color: '#3b82f6',
      fontWeight: '600',
    },
    stepIndicator: {
      flex: 1,
      textAlign: 'center',
      fontSize: 13,
      color: isDark ? '#9ca3af' : '#6b7280',
    },
    infoBox: {
      backgroundColor: isDark ? '#0f172a' : '#f0f9ff',
      borderLeftWidth: 4,
      borderLeftColor: '#3b82f6',
      padding: 12,
      borderRadius: 8,
      marginBottom: 20,
    },
    infoText: {
      fontSize: 13,
      color: isDark ? '#bfdbfe' : '#1e40af',
      lineHeight: 20,
    },
  });

  if (statusLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={[styles.content, { justifyContent: 'center' }]}>
          <ActivityIndicator size="large" color="#3b82f6" />
        </View>
      </SafeAreaView>
    );
  }

  if (!status?.enabled) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.content}>
          <Text style={styles.logo}>⚠️</Text>
          <Text style={styles.title}>{t('serviceUnavailable')}</Text>
          <Text style={styles.subtitle}>
            {t('mcareNotAvailable')}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {step !== 'language' && (
          <View style={styles.header}>
            <TouchableOpacity
              style={styles.backButton}
              onPress={handleGoBack}
            >
              <Text style={styles.backButtonText}>← {t('back')}</Text>
            </TouchableOpacity>
            <Text style={styles.stepIndicator}>
              {step === 'member' ? `${t('step')} 2/3` : `${t('step')} 3/3`}
            </Text>
            <View style={{ width: 44 }} />
          </View>
        )}

        <ScrollView contentContainerStyle={styles.content}>
          {step === 'language' && (
            <>
              <Text style={styles.logo}>🌍</Text>
              <Text style={styles.title}>{t('selectLanguage')}</Text>
              <Text style={styles.subtitle}>
                {t('languageHint')}
              </Text>

              <View style={styles.optionContainer}>
                <TouchableOpacity
                  style={[
                    styles.optionButton,
                    selectedLanguage === 'en' && styles.optionButtonActive,
                  ]}
                  onPress={() => handleLanguageSelect('en')}
                >
                  <Text
                    style={[
                      styles.optionButtonText,
                      selectedLanguage === 'en' &&
                        styles.optionButtonTextActive,
                    ]}
                  >
                    English
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.optionButton,
                    selectedLanguage === 'fr' && styles.optionButtonActive,
                  ]}
                  onPress={() => handleLanguageSelect('fr')}
                >
                  <Text
                    style={[
                      styles.optionButtonText,
                      selectedLanguage === 'fr' &&
                        styles.optionButtonTextActive,
                    ]}
                  >
                    Français
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.optionButton,
                    selectedLanguage === 'sw' && styles.optionButtonActive,
                  ]}
                  onPress={() => handleLanguageSelect('sw')}
                >
                  <Text
                    style={[
                      styles.optionButtonText,
                      selectedLanguage === 'sw' &&
                        styles.optionButtonTextActive,
                    ]}
                  >
                    Kiswahili
                  </Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          {step === 'member' && (
            <>
              <Text style={styles.logo}>💳</Text>
              <Text style={styles.title}>{t('membershipInfo')}</Text>
              <Text style={styles.subtitle}>
                {t('membershipHint')}
              </Text>

              <View style={styles.infoBox}>
                <Text style={styles.infoText}>
                  ℹ️ {t('cssaIdDescription')}
                </Text>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>{t('cssaId')}</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., CSSA12345"
                  placeholderTextColor={
                    isDark ? '#6b7280' : '#9ca3af'
                  }
                  value={cssaId}
                  onChangeText={(text) => {
                    setCssaId(text.toUpperCase());
                    setError(null);
                  }}
                  editable={!isVerifying}
                  autoCapitalize="characters"
                  returnKeyType="next"
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>
                  {t('beneficiaryName')} ({t('optional')})
                </Text>
                <TextInput
                  style={styles.input}
                  placeholder={t('namePlaceholder')}
                  placeholderTextColor={
                    isDark ? '#6b7280' : '#9ca3af'
                  }
                  value={beneficiaryName}
                  onChangeText={setBeneficiaryName}
                  editable={!isVerifying}
                  returnKeyType="done"
                />
              </View>

              {error && <Text style={styles.errorText}>{error}</Text>}

              <View style={styles.warningBox}>
                <Text style={styles.warningTitle}>
                  ⚠️ {t('importantNotice')}
                </Text>
                <Text style={styles.warningText}>
                  {t('aiDisclaimerFull')}
                </Text>
              </View>

              <View style={styles.buttonContainer}>
                <TouchableOpacity
                  style={[
                    styles.button,
                    styles.primaryButton,
                    isVerifying && styles.disabledButton,
                  ]}
                  onPress={handleVerifyMember}
                  disabled={!cssaId.trim() || isVerifying}
                >
                  {isVerifying ? (
                    <>
                      <ActivityIndicator size="small" color="#fff" />
                      <Text style={styles.primaryButtonText}>
                        {t('verifying')}
                      </Text>
                    </>
                  ) : (
                    <Text style={styles.primaryButtonText}>
                      {t('continue')}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            </>
          )}

          {step === 'consent' && (
            <>
              <Text style={styles.logo}>✓</Text>
              <Text style={styles.title}>{t('agreedTerms')}</Text>
              <Text style={styles.subtitle}>
                {t('readyToStart')}
              </Text>

              <View style={styles.consentBox}>
                <Text style={styles.consentTitle}>
                  {t('userAgreement')}
                </Text>
                <Text style={styles.consentText}>
                  {t('consentText1')}
                </Text>
                <Text style={styles.consentText}>
                  {t('consentText2')}
                </Text>
                <Text style={styles.consentText}>
                  {t('consentText3')}
                </Text>
              </View>

              <View style={styles.warningBox}>
                <Text style={styles.warningTitle}>
                  🏥 {t('medicalDisclaimer')}
                </Text>
                <Text style={styles.warningText}>
                  {t('medicalDisclaimerText')}
                </Text>
              </View>

              <View style={styles.consentBox}>
                <Text style={styles.consentTitle}>
                  {t('memberDetails')}
                </Text>
                <Text style={styles.consentText}>
                  CSSA ID: <Text style={{ fontWeight: '600' }}>{cssaId}</Text>
                </Text>
                {beneficiaryName && (
                  <Text style={styles.consentText}>
                    {t('for', { name: beneficiaryName })}
                  </Text>
                )}
              </View>

              <View style={styles.buttonContainer}>
                <TouchableOpacity
                  style={[
                    styles.button,
                    styles.primaryButton,
                  ]}
                  onPress={handleConsent}
                >
                  <Text style={styles.primaryButtonText}>
                    {t('startMCare')}
                  </Text>
                </TouchableOpacity>
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};
