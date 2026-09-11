import axios, { AxiosInstance, AxiosError } from 'axios';
import * as SecureStore from 'expo-secure-store';

export interface ClinCard {
  tags: string[];
  concern_level: 'low' | 'modere' | 'urgent';
  hypotheses: string[];
  next_step: string;
}

export interface Message {
  role: 'user' | 'mcare' | 'agent';
  content: string;
  message_type?: 'text' | 'clin_card';
  clin_card?: ClinCard;
  id?: string;
  created_at?: string;
}

export interface ConversationResponse {
  conversation_id: string;
  cssa_id: string;
  status: 'orientation' | 'collect' | 'transmitted' | 'resolved';
  intent: string;
  quota_remaining: number;
  messages: Message[];
  tags: string[];
}

export interface TransmitResponse {
  ok: boolean;
  conversation_status: string;
  proposal_id: string;
  quota_remaining: number | null;
  lisacare_url: string;
  message: string;
}

export interface MCareStatus {
  enabled: boolean;
  product: string;
  requires_active_membership: boolean;
  docs: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
  status_code?: number;
}

class MCareAPI {
  private client: AxiosInstance;
  private baseUrl: string;
  private token: string | null = null;
  private language: 'en' | 'fr' | 'sw' = 'en';

  constructor(baseUrl: string = 'http://localhost:8088') {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        config.headers['Accept-Language'] = this.language;
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ApiError>) => {
        const status = error.response?.status;

        if (status === 401) {
          await this.clearAuth();
          return Promise.reject({
            message: 'Session expired. Please log in again.',
            status_code: 401,
          });
        }

        if (status === 402) {
          return Promise.reject({
            message:
              error.response?.data?.detail ||
              'Payment required. Membership may have expired.',
            status_code: 402,
          });
        }

        if (status === 503) {
          return Promise.reject({
            message: 'MCare service unavailable. Please try again later.',
            status_code: 503,
          });
        }

        return Promise.reject(error.response?.data || error);
      }
    );
  }

  async setAuth(token: string) {
    this.token = token;
    try {
      await SecureStore.setItemAsync('mcare_token', token);
    } catch (e) {
      console.warn('Failed to store auth token securely:', e);
    }
  }

  async loadAuth() {
    try {
      const token = await SecureStore.getItemAsync('mcare_token');
      if (token) {
        this.token = token;
        return true;
      }
    } catch (e) {
      console.warn('Failed to load auth token:', e);
    }
    return false;
  }

  async clearAuth() {
    this.token = null;
    try {
      await SecureStore.deleteItemAsync('mcare_token');
    } catch (e) {
      console.warn('Failed to clear auth token:', e);
    }
  }

  setLanguage(lang: 'en' | 'fr' | 'sw') {
    this.language = lang;
  }

  async getStatus(): Promise<MCareStatus> {
    try {
      const response = await this.client.get<MCareStatus>('/api/v1/mcare/status');
      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  }

  async startConversation(
    cssaId: string,
    message: string,
    beneficiaryName?: string
  ): Promise<ConversationResponse> {
    try {
      const response = await this.client.post<ConversationResponse>(
        '/api/v1/mcare/conversations',
        {
          cssa_id: cssaId,
          beneficiary_name: beneficiaryName,
          message,
        }
      );
      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  }

  async transmit(conversationId: string): Promise<TransmitResponse> {
    try {
      const response = await this.client.post<TransmitResponse>(
        '/api/v1/mcare/conversations/transmit',
        {
          conversation_id: conversationId,
        }
      );
      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  }

  async getConversationHistory(cssaId: string): Promise<ConversationResponse[]> {
    try {
      const response = await this.client.get<ConversationResponse[]>(
        `/api/v1/mcare/conversations/${cssaId}`
      );
      return response.data;
    } catch (error) {
      throw this.normalizeError(error);
    }
  }

  private normalizeError(error: any): ApiError {
    if (error.response?.data) {
      return error.response.data;
    }

    if (error.message === 'Network Error') {
      return {
        message: 'No internet connection. Please check your network.',
        status_code: 0,
      };
    }

    if (error.code === 'ECONNABORTED') {
      return {
        message: 'Request timeout. Please try again.',
        status_code: 408,
      };
    }

    return {
      message: error.message || 'An unexpected error occurred.',
      status_code: error.status_code || 500,
    };
  }

  setBaseUrl(url: string) {
    this.baseUrl = url;
    this.client.defaults.baseURL = url;
  }
}

export const mcareAPI = new MCareAPI(process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8088');
