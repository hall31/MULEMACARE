export interface User {
  cssaId: string;
  name?: string;
  language: 'en' | 'fr' | 'sw';
}

export interface Theme {
  isDark: boolean;
  colors: {
    primary: string;
    secondary: string;
    background: string;
    text: string;
    border: string;
    success: string;
    warning: string;
    danger: string;
  };
}

export type NavigationScreenParams = {
  Onboarding: undefined;
  Chat: { cssaId: string; beneficiaryName?: string };
  History: { cssaId: string };
};
