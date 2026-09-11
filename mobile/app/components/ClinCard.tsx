import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  useColorScheme,
} from 'react-native';
import { ClinCard as ClinCardData } from '../services/mcare';
import { useTranslation } from 'react-i18next';

interface ClinCardProps {
  data: ClinCardData;
  onTransmit: () => Promise<void>;
  onTrack: () => void;
  isTransmitting?: boolean;
  quotaRemaining?: number;
}

const getConcernColor = (level: string, isDark: boolean): string => {
  const colors = {
    low: isDark ? '#10b981' : '#d1fae5',
    modere: isDark ? '#f59e0b' : '#fef3c7',
    urgent: isDark ? '#ef4444' : '#fee2e2',
  };
  return colors[level as keyof typeof colors] || (isDark ? '#6b7280' : '#f3f4f6');
};

const getConcernTextColor = (level: string, isDark: boolean): string => {
  const colors = {
    low: isDark ? '#d1fae5' : '#065f46',
    modere: isDark ? '#fef3c7' : '#92400e',
    urgent: isDark ? '#fee2e2' : '#7f1d1d',
  };
  return colors[level as keyof typeof colors] || (isDark ? '#e5e7eb' : '#374151');
};

export const ClinCard: React.FC<ClinCardProps> = ({
  data,
  onTransmit,
  onTrack,
  isTransmitting = false,
  quotaRemaining,
}) => {
  const { t } = useTranslation();
  const isDark = useColorScheme() === 'dark';
  const [expanded, setExpanded] = useState(true);

  const styles = StyleSheet.create({
    container: {
      backgroundColor: isDark ? '#1f2937' : '#fff',
      borderRadius: 12,
      padding: 16,
      marginVertical: 12,
      marginHorizontal: 16,
      borderLeftWidth: 4,
      borderLeftColor:
        data.concern_level === 'urgent'
          ? '#ef4444'
          : data.concern_level === 'modere'
            ? '#f59e0b'
            : '#10b981',
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 8,
      elevation: 3,
    },
    header: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 12,
    },
    titleRow: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    title: {
      fontSize: 18,
      fontWeight: '700',
      color: isDark ? '#f3f4f6' : '#1f2937',
    },
    concernBadge: {
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: 6,
      backgroundColor: getConcernColor(data.concern_level, isDark),
    },
    concernText: {
      fontSize: 12,
      fontWeight: '600',
      color: getConcernTextColor(data.concern_level, isDark),
      textTransform: 'uppercase',
    },
    tagContainer: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 6,
      marginBottom: 12,
    },
    tag: {
      backgroundColor: isDark ? '#374151' : '#f3f4f6',
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 4,
    },
    tagText: {
      fontSize: 11,
      color: isDark ? '#9ca3af' : '#6b7280',
      fontWeight: '500',
    },
    section: {
      marginBottom: 12,
    },
    sectionTitle: {
      fontSize: 14,
      fontWeight: '600',
      color: isDark ? '#d1d5db' : '#374151',
      marginBottom: 8,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    hypothesisList: {
      gap: 8,
    },
    hypothesisItem: {
      backgroundColor: isDark ? '#111827' : '#f9fafb',
      padding: 10,
      borderRadius: 8,
      borderLeftWidth: 3,
      borderLeftColor: isDark ? '#4b5563' : '#dbeafe',
    },
    hypothesisText: {
      fontSize: 14,
      color: isDark ? '#e5e7eb' : '#1f2937',
      lineHeight: 20,
    },
    nextStepBox: {
      backgroundColor: isDark ? '#111827' : '#f0f9ff',
      padding: 12,
      borderRadius: 8,
      borderLeftWidth: 3,
      borderLeftColor: '#3b82f6',
    },
    nextStepText: {
      fontSize: 13,
      color: isDark ? '#e5e7eb' : '#1e40af',
      lineHeight: 20,
      fontStyle: 'italic',
    },
    actionContainer: {
      flexDirection: 'row',
      gap: 10,
      marginTop: 16,
      borderTopWidth: 1,
      borderTopColor: isDark ? '#374151' : '#e5e7eb',
      paddingTop: 16,
    },
    button: {
      flex: 1,
      paddingVertical: 12,
      paddingHorizontal: 16,
      borderRadius: 8,
      justifyContent: 'center',
      alignItems: 'center',
      flexDirection: 'row',
      gap: 8,
    },
    transmitButton: {
      backgroundColor: '#ef4444',
    },
    trackButton: {
      backgroundColor: isDark ? '#374151' : '#e5e7eb',
    },
    buttonText: {
      fontSize: 14,
      fontWeight: '600',
    },
    transmitButtonText: {
      color: '#fff',
    },
    trackButtonText: {
      color: isDark ? '#f3f4f6' : '#1f2937',
    },
    disabledButton: {
      opacity: 0.5,
    },
    quotaWarning: {
      backgroundColor: isDark ? '#7f1d1d' : '#fee2e2',
      paddingHorizontal: 10,
      paddingVertical: 8,
      borderRadius: 6,
      marginTop: 8,
    },
    quotaWarningText: {
      fontSize: 12,
      color: isDark ? '#fca5a5' : '#991b1b',
      fontWeight: '500',
    },
    loadingOverlay: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      borderRadius: 12,
      justifyContent: 'center',
      alignItems: 'center',
    },
  });

  return (
    <View style={[styles.container, isTransmitting && { opacity: 0.8 }]}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Clinical Assessment</Text>
          <View style={styles.concernBadge}>
            <Text style={styles.concernText}>
              {data.concern_level === 'urgent'
                ? t('urgent')
                : data.concern_level === 'modere'
                  ? t('moderate')
                  : t('low')}
            </Text>
          </View>
        </View>
        <TouchableOpacity onPress={() => setExpanded(!expanded)}>
          <Text style={{ fontSize: 18, color: isDark ? '#9ca3af' : '#6b7280' }}>
            {expanded ? '−' : '+'}
          </Text>
        </TouchableOpacity>
      </View>

      {data.tags && data.tags.length > 0 && (
        <View style={styles.tagContainer}>
          {data.tags.map((tag, idx) => (
            <View key={idx} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}

      {expanded && (
        <>
          {data.hypotheses && data.hypotheses.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t('hypothesis')}</Text>
              <View style={styles.hypothesisList}>
                {data.hypotheses.map((hyp, idx) => (
                  <View key={idx} style={styles.hypothesisItem}>
                    <Text style={styles.hypothesisText}>• {hyp}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {data.next_step && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t('nextStep')}</Text>
              <View style={styles.nextStepBox}>
                <Text style={styles.nextStepText}>{data.next_step}</Text>
              </View>
            </View>
          )}

          <View style={styles.actionContainer}>
            <TouchableOpacity
              style={[
                styles.button,
                styles.transmitButton,
                (isTransmitting || (quotaRemaining !== undefined && quotaRemaining <= 0)) &&
                  styles.disabledButton,
              ]}
              onPress={onTransmit}
              disabled={isTransmitting || (quotaRemaining !== undefined && quotaRemaining <= 0)}
            >
              {isTransmitting ? (
                <>
                  <ActivityIndicator size="small" color="#fff" />
                  <Text style={[styles.buttonText, styles.transmitButtonText]}>
                    {t('transmitting')}
                  </Text>
                </>
              ) : (
                <Text style={[styles.buttonText, styles.transmitButtonText]}>
                  {t('seeDoctorButton')}
                </Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.trackButton]}
              onPress={onTrack}
              disabled={isTransmitting}
            >
              <Text style={[styles.buttonText, styles.trackButtonText]}>
                {t('trackSymptoms')}
              </Text>
            </TouchableOpacity>
          </View>

          {quotaRemaining !== undefined && quotaRemaining <= 1 && (
            <View style={styles.quotaWarning}>
              <Text style={styles.quotaWarningText}>
                {t('quotaWarning', { remaining: quotaRemaining })}
              </Text>
            </View>
          )}

          <Text
            style={{
              fontSize: 11,
              color: isDark ? '#9ca3af' : '#6b7280',
              marginTop: 12,
              fontStyle: 'italic',
            }}
          >
            ⓘ {t('aiDisclaimer')}
          </Text>
        </>
      )}

      {isTransmitting && (
        <View style={styles.loadingOverlay} pointerEvents="none" />
      )}
    </View>
  );
};
