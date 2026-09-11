import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  useColorScheme,
  SafeAreaView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { mcareAPI, ConversationResponse } from '../services/mcare';
import { useTranslation } from 'react-i18next';
import { formatDistanceToNow } from 'date-fns';
import { frLocale } from 'date-fns/locale';

interface HistoryProps {
  cssaId: string;
  onSelectConversation: (conversation: ConversationResponse) => void;
  onBack: () => void;
}

export const MCareHistory: React.FC<HistoryProps> = ({
  cssaId,
  onSelectConversation,
  onBack,
}) => {
  const { t, i18n } = useTranslation();
  const isDark = useColorScheme() === 'dark';
  const [refreshing, setRefreshing] = useState(false);

  const { data: conversations, isLoading, refetch } = useQuery({
    queryKey: ['mcare-history', cssaId],
    queryFn: () => mcareAPI.getConversationHistory(cssaId),
    enabled: !!cssaId,
  });

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'transmitted':
        return '#10b981';
      case 'orientation':
        return '#f59e0b';
      case 'resolved':
        return '#3b82f6';
      default:
        return '#6b7280';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'transmitted':
        return t('statusTransmitted');
      case 'orientation':
        return t('statusNeedsReview');
      case 'resolved':
        return t('statusResolved');
      default:
        return t('statusCollecting');
    }
  };

  const getSummaryText = (conv: ConversationResponse) => {
    const lastMessage = conv.messages[conv.messages.length - 1];
    return lastMessage?.content?.substring(0, 80) || t('noMessages');
  };

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
      alignItems: 'center',
      gap: 12,
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
    headerTitle: {
      fontSize: 18,
      fontWeight: '700',
      color: isDark ? '#f3f4f6' : '#1f2937',
      flex: 1,
    },
    content: {
      flex: 1,
    },
    emptyState: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      paddingHorizontal: 32,
    },
    emptyStateText: {
      fontSize: 16,
      fontWeight: '500',
      color: isDark ? '#9ca3af' : '#6b7280',
      textAlign: 'center',
      lineHeight: 24,
      marginBottom: 8,
    },
    emptyStateSubtext: {
      fontSize: 13,
      color: isDark ? '#6b7280' : '#9ca3af',
      textAlign: 'center',
    },
    conversationCard: {
      marginHorizontal: 12,
      marginVertical: 8,
      paddingHorizontal: 16,
      paddingVertical: 12,
      backgroundColor: isDark ? '#1f2937' : '#f9fafb',
      borderRadius: 10,
      borderLeftWidth: 4,
      borderLeftColor: '#3b82f6',
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.05,
      shadowRadius: 4,
      elevation: 1,
    },
    cardHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 8,
    },
    beneficiaryName: {
      fontSize: 15,
      fontWeight: '600',
      color: isDark ? '#f3f4f6' : '#1f2937',
      flex: 1,
    },
    statusBadge: {
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 4,
    },
    statusBadgeText: {
      fontSize: 11,
      fontWeight: '600',
      color: '#fff',
    },
    cardBody: {
      marginBottom: 8,
    },
    summary: {
      fontSize: 13,
      color: isDark ? '#d1d5db' : '#374151',
      lineHeight: 18,
      marginBottom: 6,
    },
    cardFooter: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingTopWidth: 1,
      borderTopColor: isDark ? '#374151' : '#e5e7eb',
      paddingTop: 8,
    },
    timestamp: {
      fontSize: 12,
      color: isDark ? '#6b7280' : '#9ca3af',
    },
    messageCount: {
      fontSize: 12,
      fontWeight: '500',
      color: isDark ? '#9ca3af' : '#6b7280',
    },
    divider: {
      height: 1,
      backgroundColor: isDark ? '#374151' : '#e5e7eb',
      marginVertical: 8,
    },
    loadingContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
    },
  });

  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={onBack}>
            <Text style={styles.backButtonText}>← {t('back')}</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{t('conversations')}</Text>
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3b82f6" />
        </View>
      </SafeAreaView>
    );
  }

  const sortedConversations = [...(conversations || [])]
    .sort((a, b) => {
      const aTime = a.messages[a.messages.length - 1]?.created_at || '';
      const bTime = b.messages[b.messages.length - 1]?.created_at || '';
      return new Date(bTime).getTime() - new Date(aTime).getTime();
    });

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Text style={styles.backButtonText}>← {t('back')}</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('conversationHistory')}</Text>
      </View>

      {sortedConversations.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyStateText}>{t('noConversations')}</Text>
          <Text style={styles.emptyStateSubtext}>
            {t('startFirstConversation')}
          </Text>
        </View>
      ) : (
        <FlatList
          data={sortedConversations}
          keyExtractor={(item) => item.conversation_id}
          renderItem={({ item }) => {
            const lastMessage = item.messages[item.messages.length - 1];
            const messageTime = lastMessage?.created_at
              ? new Date(lastMessage.created_at)
              : new Date();

            return (
              <TouchableOpacity
                style={styles.conversationCard}
                onPress={() => onSelectConversation(item)}
                activeOpacity={0.7}
              >
                <View style={styles.cardHeader}>
                  <Text style={styles.beneficiaryName}>
                    {item.beneficiary_name || item.cssa_id}
                  </Text>
                  <View
                    style={[
                      styles.statusBadge,
                      { backgroundColor: getStatusColor(item.status) },
                    ]}
                  >
                    <Text style={styles.statusBadgeText}>
                      {getStatusLabel(item.status)}
                    </Text>
                  </View>
                </View>

                <View style={styles.cardBody}>
                  <Text style={styles.summary} numberOfLines={2}>
                    {getSummaryText(item)}
                  </Text>
                </View>

                <View style={styles.cardFooter}>
                  <Text style={styles.timestamp}>
                    {formatDistanceToNow(messageTime, {
                      addSuffix: true,
                      locale: i18n.language === 'fr' ? frLocale : undefined,
                    })}
                  </Text>
                  <Text style={styles.messageCount}>
                    {item.messages.length} {t('messages')}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          }}
          contentContainerStyle={{ paddingVertical: 8 }}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        />
      )}
    </SafeAreaView>
  );
};
