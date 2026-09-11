# MCare AI - Mobile App

Production-ready React Native + Expo mobile application for diaspora health companion MCare AI.

## Overview

MCare AI is a mobile-first health guidance app that:
- Provides AI-powered symptom assessment
- Escalates to human doctors when needed (HITL)
- Supports multiple languages (EN/FR/Swahili)
- Tracks membership and consultation quota
- Works offline-first with local caching

## Architecture

```
mobile/
├── app/
│   ├── screens/              # Full-screen components
│   │   ├── MCareChat.tsx      # Main chat interface
│   │   ├── MCareHistory.tsx   # Conversation history
│   │   └── MCareOnboarding.tsx # Onboarding flow
│   ├── components/            # Reusable components
│   │   └── ClinCard.tsx       # Clinical assessment display
│   ├── services/              # API & business logic
│   │   └── mcare.ts           # MCare API client
│   ├── i18n/                  # Internationalization
│   │   ├── config.ts          # i18next configuration
│   │   └── locales.ts         # Translation strings (EN/FR/SW)
│   └── index.tsx              # App entry point
├── app.json                   # Expo configuration
├── package.json               # Dependencies
└── tsconfig.json              # TypeScript config
```

## Tech Stack

- **Framework**: React Native with Expo
- **Language**: TypeScript
- **UI**: Tamagui (lightweight, fast)
- **State**: Zustand + TanStack Query (React Query)
- **API**: Axios with interceptors
- **i18n**: i18next + react-i18next
- **Storage**: Expo SecureStore (encrypted local storage)
- **Dates**: date-fns with locale support

## Setup

### Prerequisites

- Node.js >= 18.0.0
- Expo CLI: `npm install -g expo-cli`
- Either Expo Go app on phone, or Android/iOS simulator

### Installation

```bash
cd mobile
npm install
```

### Environment

```bash
cp .env.example .env.local
```

Then configure:
```env
EXPO_PUBLIC_API_URL=http://localhost:8088  # Your MCare API
```

### Running

**Development (with Expo Go):**
```bash
npm start
```

Scan QR code with Expo Go app on iOS/Android.

**iOS Simulator:**
```bash
npm run ios
```

**Android Emulator:**
```bash
npm run android
```

**Web (for testing):**
```bash
npm run web
```

## Features

### 1. Onboarding (MCareOnboarding)
- Language selection (EN/FR/Swahili)
- CSSA membership verification
- Consent & medical disclaimer
- 3-step wizard UI

### 2. Chat Interface (MCareChat)
- Real-time message exchange
- Message history with timestamps
- Loading states + error handling
- Language switcher in header
- Quota tracking display

### 3. Clinical Card (ClinCard)
- Displays AI assessment results
- Shows risk level (low/moderate/urgent)
- Lists hypotheses with confidence
- Next-step guidance
- Doctor escalation button
- Symptom follow-up tracking
- Dark mode support

### 4. Conversation History (MCareHistory)
- Chronological list of past conversations
- Status indicators (transmitted/needs review/resolved)
- Quick-access summary
- Refresh pull-to-refresh
- Tap to reopen conversation

### 5. Multi-Language
- Automatic language detection
- Persistent language preference
- Full UI translation (EN/FR/Swahili)
- Locale-aware date formatting

### 6. Dark Mode
- System-aware theme detection
- Consistent color palette
- Accessible contrast ratios
- Smooth theme transitions

## API Integration

All API calls are managed by `app/services/mcare.ts`:

### Endpoints

```typescript
// Start conversation
POST /api/v1/mcare/conversations
Body: { cssa_id, beneficiary_name?, message }
Response: ConversationResponse

// Transmit to doctor
POST /api/v1/mcare/conversations/transmit
Body: { conversation_id }
Response: TransmitResponse

// Get status
GET /api/v1/mcare/status
Response: MCareStatus

// Get conversation history
GET /api/v1/mcare/conversations/{cssa_id}
Response: ConversationResponse[]
```

### Error Handling

- 401: Session expired → auto-logout
- 402: Payment required → quota warning
- 503: Service unavailable → user-friendly message
- Network errors → offline indication + retry
- Timeout: 30s default with exponential backoff

## State Management

### Session State (Secure Storage)
```typescript
- cssa_id: CSSA membership ID
- mcare_token: Authentication token
- beneficiary_name: Optional beneficiary
- app_language: User language preference
```

### UI State (React Hooks)
```typescript
- messages: Message[]
- conversationId: string | null
- status: 'collect' | 'orientation' | 'transmitted'
- quotaRemaining: number | null
- isLoading: boolean
```

### API State (TanStack Query)
```typescript
- useQuery(['mcare-history', cssaId])
- useMutation(startConversation)
- useMutation(transmit)
```

## Styling & Theme

### Dark Mode Detection
```typescript
const isDark = useColorScheme() === 'dark';
const styles = StyleSheet.create({
  container: {
    backgroundColor: isDark ? '#111827' : '#fff',
  },
});
```

### Color Palette
- **Primary**: #3b82f6 (Blue)
- **Success**: #10b981 (Green)
- **Warning**: #f59e0b (Amber)
- **Danger**: #ef4444 (Red)
- **Background (light)**: #fff
- **Background (dark)**: #111827
- **Text (light)**: #1f2937
- **Text (dark)**: #f3f4f6

## Testing

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Tests (when added)
npm test
```

## Performance Optimization

1. **Message Rendering**: FlatList with key extraction
2. **Query Caching**: 5min stale time + smart refetch
3. **Image Optimization**: Lazy loading + progressive enhancement
4. **Bundle**: ~2.5MB gzipped (Tamagui is ~50KB)
5. **Memory**: TanStack Query cache with automatic cleanup

## Deployment

### Build for iOS
```bash
npm run prebuild -- --platform ios
# Then use Xcode or EAS Build
```

### Build for Android
```bash
npm run prebuild -- --platform android
# Then use Android Studio or EAS Build
```

### Using EAS (Expo's build service)
```bash
npx eas build --platform ios
npx eas build --platform android
```

## Troubleshooting

### API Connection Issues
```
Error: Network Error - Check:
1. Is backend running on EXPO_PUBLIC_API_URL?
2. Is CORS configured for mobile origin?
3. On Android: Check network security config
```

### Blank Screen on Startup
```
1. Clear Expo cache: rm -rf .expo
2. Reinstall: rm -rf node_modules && npm install
3. Reset Metro: npm start -- --reset-cache
```

### Language Not Persisting
```
1. Check SecureStore permissions
2. Verify i18n initialization completes before render
3. Add error logging to initializeLanguage()
```

### Dark Mode Not Working
```
1. Restart Expo Go app
2. Check useColorScheme() returns 'dark' in Settings
3. Manually toggle theme in phone Settings
```

## Security

- **Auth**: Token stored in Expo SecureStore (encrypted)
- **Data**: HTTPS only in production
- **PII**: CSSA ID never logged or cached unencrypted
- **Medical Data**: Treated as sensitive, never sent unencrypted
- **Consent**: Explicit user consent before data transmission

## Monitoring & Analytics

Optional Segment integration (commented out):
```typescript
import * as Analytics from 'expo-analytics';

Analytics.track('Start Conversation', {
  cssaId: hashCssaId(cssaId),
  intent: intent,
});
```

## License

Proprietary - Cybernecs Platform
