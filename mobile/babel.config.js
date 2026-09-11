module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      [
        'module-resolver',
        {
          extensions: ['.tsx', '.ts', '.js', '.json'],
          alias: {
            '@': './app',
            '@screens': './app/screens',
            '@components': './app/components',
            '@services': './app/services',
            '@hooks': './app/hooks',
            '@types': './app/types',
            '@utils': './app/utils',
            '@i18n': './app/i18n',
          },
        },
      ],
    ],
  };
};
