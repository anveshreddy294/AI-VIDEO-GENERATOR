import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
  // Existing prop/local-storage synchronization is intentionally retained.
  // New learning components remain subject to all recommended hook rules.
  {
    files: ['src/components/MarkdownEditor.jsx', 'src/components/VideoPlayer.jsx',
      'src/screens/Dashboard.jsx', 'src/screens/Health.jsx', 'src/screens/Library.jsx',
      'src/screens/ScriptInspector.jsx'],
    rules: { 'react-hooks/set-state-in-effect': 'off' },
  },
  {
    files: ['src/screens/KnowledgeGraph.jsx'],
    rules: { 'react-hooks/immutability': 'off' },
  },
  {
    files: ['src/context/ProfileContext.jsx', 'src/context/SessionContext.jsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
