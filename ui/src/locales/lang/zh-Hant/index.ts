import zhTw from 'element-plus/es/locale/lang/zh-tw'
import components from './components'
import layout from './layout'
import views from './views'
import theme from './theme'
import common from './common'
import dynamicsForm from './dynamics-form'
import aiChat from './ai-chat'
import workflow from './workflow'
import home from './home'
import runTrace from './run-trace'
export default {
  runTrace,
  studio: {
    navigation: '主導覽',
    sidebar: '側邊導覽',
    accountMenu: '帳戶選單',
    actions: '操作',
    findProvider: '搜尋供應商',
    noModels: '尚未新增模型',
    noMatchingModels: '沒有符合的模型',
    console: 'RAG Agent 控制台',
    client: '產品呼叫方',
    iteration: '迭代',
    attempt: '嘗試',
    elapsed: '耗時（秒）',
    outputRef: '輸出參照',
    unavailableNodes: '此工作流程包含未啟用的節點，編輯已停用。',
    runs: '執行記錄',
    brand: '系統品牌',
    name: '系統名稱',
    icon: '系統圖示',
    chooseIcon: '選擇圖示',
    resetIcon: '恢復預設圖示',
    iconError: '請選擇不超過 512 × 512 和 256 KiB 的靜態 PNG 圖片',
    saved: '已儲存',
    refresh: '重新整理',
    noRuns: '尚無執行記錄',
    status: '狀態',
    subject: '呼叫使用者',
    started: '建立時間',
    trace: '執行軌跡',
    session: '工作階段',
    steps: '節點執行',
    events: '事件',
    output: '執行結果',
  },
  lang: '繁體中文',
  layout,
  views,
  theme,
  common,
  components,
  zhTw,
  dynamicsForm,
  aiChat,
  workflow,
  home,
}
