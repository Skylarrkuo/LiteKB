import zhCn from 'element-plus/es/locale/lang/zh-cn'
import components from './components'
import views from './views'
import theme from './theme'
import layout from './layout'
import dynamicsForm from './dynamics-form'
import common from './common'
import aiChat from './ai-chat'
import workflow from './workflow'
import home from './home'
import runTrace from './run-trace'
export default {
  runTrace,
  studio: {
    navigation: '主导航',
    sidebar: '侧边导航',
    accountMenu: '账户菜单',
    actions: '操作',
    findProvider: '搜索供应商',
    noModels: '尚未添加模型',
    noMatchingModels: '没有匹配的模型',
    console: 'RAG Agent 控制台',
    client: '产品调用方',
    iteration: '迭代',
    attempt: '尝试',
    elapsed: '耗时（秒）',
    outputRef: '输出引用',
    unavailableNodes: '此工作流包含未启用的节点，编辑已停用。',
    runs: '运行记录',
    brand: '系统品牌',
    name: '系统名称',
    icon: '系统图标',
    chooseIcon: '选择图标',
    resetIcon: '恢复默认图标',
    iconError: '请选择不超过 512 × 512 和 256 KiB 的静态 PNG 图片',
    saved: '已保存',
    refresh: '刷新',
    noRuns: '暂无运行记录',
    status: '状态',
    subject: '调用用户',
    started: '创建时间',
    trace: '运行轨迹',
    session: '会话',
    steps: '节点执行',
    events: '事件',
    output: '执行结果',
  },
  lang: '简体中文',
  zhCn,
  views,
  theme,
  layout,
  dynamicsForm,
  common,
  aiChat,
  components,
  workflow,
  home,
}
