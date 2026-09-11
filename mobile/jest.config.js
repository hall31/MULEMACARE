module.exports = {
  preset: 'jest-expo',
  testEnvironment: 'node',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  collectCoverageFrom: [
    'app/**/*.{ts,tsx}',
    '!app/**/*.d.ts',
    '!app/**/index.ts',
  ],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/app/$1',
    '^@screens/(.*)$': '<rootDir>/app/screens/$1',
    '^@components/(.*)$': '<rootDir>/app/components/$1',
    '^@services/(.*)$': '<rootDir>/app/services/$1',
    '^@hooks/(.*)$': '<rootDir>/app/hooks/$1',
    '^@types/(.*)$': '<rootDir>/app/types/$1',
    '^@utils/(.*)$': '<rootDir>/app/utils/$1',
    '^@i18n/(.*)$': '<rootDir>/app/i18n/$1',
  },
  transform: {
    '^.+\\.(ts|tsx)$': ['babel-jest', { presets: ['babel-preset-expo'] }],
  },
  testMatch: [
    '<rootDir>/app/**/__tests__/**/*.ts?(x)',
    '<rootDir>/app/**/?(*.)+(spec|test).ts?(x)',
  ],
};
