import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  useColorScheme,
  SafeAreaView,
  FlatList,
  Dimensions,
} from 'react-native';
import { useMutation, useQuery } from '@tanstack/react-query';
import { mcareAPI, Message, ConversationResponse } from '../services/mcare';
import { ClinCard } from '../components/ClinCard';
import { useTranslation } from 'react-i18next';

interface ChatProps {
  cssaId: string;
  beneficiaryName?: string;
  onBack: () => void;
}

export const MCareChat: React.FC<ChatProps> = ({
  cssaId,
  beneficiaryName,
  onBack,
}) => {
  const { t, i18n } = useTranslation();
  const isDark = useColorScheme() === 'dark';
  const scrollViewRef = useRef<ScrollView>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [status, setStatus] = useState<'collect' | 'orientation' | 'transmitted'>('collect');
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null);

  const screenWidth = Dimensions.get('window').width;

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: isDark ? '#111827' : '#fff',
    },
    header: {
      backgroundColor: isDark ? '#1f2937' : '#f9fafb',
      borderBottomWidth: 1,
      borderBottomColor: isDark ? '#374151' : '#e5e7eb',
      paddingHorizontal: 16,
      paddingVertical: 12,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    headerContent: {
      flex: 1,
    },
    headerTitle: {
      fontSize: 18,
      fontWeight: '700',
      color: isDark ? '#f3f4f6' : '#1f2937',
    },
    headerSubtitle: {
      fontSize: 12,
      color: isDark ? '#9ca3af' : '#6b7280',
      marginTop: 2,
    },
    languageSwitcher: {
      flexDirection: 'row',
      gap: 4,
    },
    langButton: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 6,
      backgroundColor: isDark ? '#374151' : '#e5e7eb',
    },
    langButtonActive: {
      backgroundColor: '#3b82f6',
    },
    langButtonText: {
      fontSize: 11,
      fontWeight: '600',
      color: isDark ? '#e5e7eb' : '#1f2937',
    },
    langButtonTextActive: {
      color: '#fff',
    },
    messagesContainer: {
      flex: 1,
      paddingVertical: 12,
    },
    messageRow: {
      marginVertical: 8,
      paddingHorizontal: 16,
    },
    messageBubble: {
      maxWidth: screenWidth * 0.85,
      padding: 12,
      borderRadius: 12,
    },
    userBubble: {
      alignSelf: 'flex-end',
      backgroundColor: '#3b82f6',
    },
    agentBubble: {
      alignSelf: 'flex-start',
      backgroundColor: isDark ? '#374151' : '#f3f4f6',
    },
    userText: {
      color: '#fff',
      fontSize: 14,
      lineHeight: 20,
    },
    agentText: {
      color: isDark ? '#e5e7eb' : '#1f2937',
      fontSize: 14,
      lineHeight: 20,
    },
    messageTimestamp: {
      fontSize: 11,
      color: isDark ? '#6b7280' : '#9ca3af',
      marginTop: 4,
    },
    inputContainer: {
      backgroundColor: isDark ? '#1f2937' : '#f9fafb',
      borderTopWidth: 1,
      borderTopColor: isDark ? '#374151' : '#e5e7eb',
      paddingHorizontal: 12,
      paddingVertical: 12,
      gap: 8,
    },
    inputRow: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      gap: 8,
    },
    input: {
      flex: 1,
      backgroundColor: isDark ? '#111827' : '#fff',
      borderWidth: 1,
      borderColor: isDark ? '#374151' : '#e5e7eb',
      borderRadius: 8,
      paddingHorizontal: 12,
      paddingVertical: 10,
      color: isDark ? '#f3f4f6' : '#1f2937',
      fontSize: 14,
      maxHeight: 100,
    },
    sendButton: {
      backgroundColor: '#3b82f6',
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderRadius: 8,
      justifyContent: 'center',
      alignItems: 'center',
    },
    sendButtonDisabled: {
      opacity: 0.5,
    },
    sendButtonText: {
      color: '#fff',
      fontWeight: '600',
      fontSize: 12,
    },
    statusBadge: {
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: 4,
      alignSelf: 'flex-start',
      marginHorizontal: 16,
      marginBottom: 12,
    },
    statusBadgeText: {
      fontSize: 11,
      fontWeight: '600',
      color: '#fff',
    },
    loadingIndicator: {
      paddingHorizontal: 16,
      paddingVertical: 12,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    loadingText: {
      fontSize: 13,
      color: isDark ? '#9ca3af' : '#6b7280',
      fontStyle: 'italic',
    },
    emptyState: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      paddingHorizontal: 32,
    },
    emptyStateText: {
      fontSize: 14,
      color: isDark ? '#9ca3af' : '#6b7280',
      textAlign: 'center',
      lineHeight: 20,
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
  });

  const startConversationMutation = useMutation({
    mutationFn: (message: string) =>
      mcareAPI.startConversation(cssaId, message, beneficiaryName),
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      setMessages(data.messages);
      setStatus(data.status);
      setQuotaRemaining(data.quota_remaining);
    },
  });

  const transmitMutation = useMutation({
    mutationFn: () => conversationId && mcareAPI.transmit(conversationId),
    onSuccess: (data) => {
      if (data) {
        setStatus(data.conversation_status as any);
        setQuotaRemaining(data.quota_remaining);
      }
    },
  });

  const handleSendMessage = () => {
    if (inputValue.trim().length === 0) return;

    const userMessage: Message = {
      role: 'user',
      content: inputValue,
      message_type: 'text',
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    startConversationMutation.mutate(inputValue);
  };

  const handleTransmit = async () => {
    await transmitMutation.mutateAsync();
  };

  const handleTrackSymptoms = () => {
    const followUpMessage = t('followUpPrompt');
    handleSendMessage();
  };

  const getStatusBadgeColor = () => {
    if (status === 'transmitted') return '#10b981';
    if (status === 'orientation') return '#3b82f6';
    return '#6b7280';
  };

  useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  const isLoading = startConversationMutation.isPending;
  const isTransmitting = transmitMutation.isPending;

  const clinCardMessage = messages.find((m) => m.message_type === 'clin_card');

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={onBack}>
            <Text style={styles.backButtonText}>← {t('back')}</Text>
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <Text style={styles.headerTitle}>MCare AI</Text>
            <Text style={styles.headerSubtitle}>
              {beneficiaryName ? t('for', { name: beneficiaryName }) : cssaId}
            </Text>
          </View>
          <View style={styles.languageSwitcher}>
            {['en', 'fr', 'sw'].map((lang) => (
              <TouchableOpacity
                key={lang}
                style={[
                  styles.langButton,
                  i18n.language === lang && styles.langButtonActive,
                ]}
                onPress={() => i18n.changeLanguage(lang)}
              >
                <Text
                  style={[
                    styles.langButtonText,
                    i18n.language === lang && styles.langButtonTextActive,
                  ]}
                >
                  {lang.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {status !== 'collect' && (
          <View style={[styles.statusBadge, { backgroundColor: getStatusBadgeColor() }]}>
            <Text style={styles.statusBadgeText}>
              {status === 'transmitted'
                ? t('transmitted')
                : status === 'orientation'
                  ? t('needsReview')
                  : t('status')}
            </Text>
          </View>
        )}

        <ScrollView
          ref={scrollViewRef}
          style={styles.messagesContainer}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.length === 0 && !isLoading ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyStateText}>{t('startConversation')}</Text>
            </View>
          ) : (
            <>
              {messages.map((msg, idx) => {
                if (msg.message_type === 'clin_card' && msg.clin_card) {
                  return (
                    <View key={idx} style={{ paddingHorizontal: 8 }}>
                      <ClinCard
                        data={msg.clin_card}
                        onTransmit={handleTransmit}
                        onTrack={handleTrackSymptoms}
                        isTransmitting={isTransmitting}
                        quotaRemaining={quotaRemaining || undefined}
                      />
                    </View>
                  );
                }

                return (
                  <View key={idx} style={styles.messageRow}>
                    <View
                      style={[
                        styles.messageBubble,
                        msg.role === 'user' ? styles.userBubble : styles.agentBubble,
                      ]}
                    >
                      <Text
                        style={msg.role === 'user' ? styles.userText : styles.agentText}
                      >
                        {msg.content}
                      </Text>
                      {msg.created_at && (
                        <Text style={styles.messageTimestamp}>
                          {new Date(msg.created_at).toLocaleTimeString()}
                        </Text>
                      )}
                    </View>
                  </View>
                );
              })}
              {isLoading && (
                <View style={styles.loadingIndicator}>
                  <ActivityIndicator size="small" color="#3b82f6" />
                  <Text style={styles.loadingText}>{t('agentThinking')}</Text>
                </View>
              )}
            </>
          )}
        </ScrollView>

        <View style={styles.inputContainer}>
          {status !== 'transmitted' && (
            <View style={styles.inputRow}>
              <TextInput
                style={styles.input}
                placeholder={t('messagePlaceholder')}
                placeholderTextColor={isDark ? '#6b7280' : '#9ca3af'}
                value={inputValue}
                onChangeText={setInputValue}
                editable={!isLoading && status !== 'transmitted'}
                multiline
                maxLength={4000}
              />
              <TouchableOpacity
                style={[
                  styles.sendButton,
                  (isLoading || inputValue.trim().length === 0) && styles.sendButtonDisabled,
                ]}
                onPress={handleSendMessage}
                disabled={isLoading || inputValue.trim().length === 0}
              >
                {isLoading ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.sendButtonText}>↗</Text>
                )}
              </TouchableOpacity>
            </View>
          )}
          {quotaRemaining !== undefined && quotaRemaining > 0 && (
            <Text
              style={{
                fontSize: 11,
                color: isDark ? '#6b7280' : '#9ca3af',
                textAlign: 'right',
              }}
            >
              {t('quotaRemaining', { count: quotaRemaining })}
            </Text>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};
