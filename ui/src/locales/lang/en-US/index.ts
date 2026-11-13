import en from 'element-plus/es/locale/lang/en'
import components from './components'
import layout from './layout'
import views from './views'
import theme from './theme'
import common from './common'
import dynamicsForm from './dynamics-form'
import aiChat from './ai-chat'
import workflow from './workflow'
import home from './home.ts'
import runTrace from './run-trace'
export default {
  runTrace,
  studio: {
    navigation: 'Main navigation',
    sidebar: 'Sidebar',
    accountMenu: 'Account menu',
    actions: 'Actions',
    findProvider: 'Find a provider',
    noModels: 'No models added yet',
    noMatchingModels: 'No matching models',
    console: 'RAG Agent console',
    client: 'Client',
    iteration: 'Iteration',
    attempt: 'Attempt',
    elapsed: 'Elapsed (s)',
    outputRef: 'Output reference',
    unavailableNodes: 'This workflow uses unavailable nodes. Editing is disabled.',
    runs: 'Runs',
    brand: 'Branding',
    name: 'System name',
    icon: 'System icon',
    chooseIcon: 'Choose icon',
    resetIcon: 'Restore default icon',
    iconError: 'Choose a static PNG up to 512 × 512 and 256 KiB.',
    saved: 'Saved',
    refresh: 'Refresh',
    noRuns: 'No runs yet',
    status: 'Status',
    subject: 'Subject',
    started: 'Created',
    trace: 'Run trace',
    session: 'Session',
    steps: 'Steps',
    events: 'Events',
    output: 'Result',
  },
  lang: 'English',
  layout,
  views,
  theme,
  components,
  en,
  common,
  dynamicsForm,
  aiChat,
  workflow,
  home,
}
