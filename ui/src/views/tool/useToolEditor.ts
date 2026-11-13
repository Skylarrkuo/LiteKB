import { computed, ref, shallowRef } from 'vue'
import type { FormInstance } from 'element-plus'
import { cloneDeep, isEqual } from 'lodash'
import { useRoute } from 'vue-router'
import type { toolData } from '@/api/type/tool'
import { t } from '@/locales'
import permissionMap from '@/permission'
import useStore from '@/stores'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { MsgConfirm, MsgSuccess } from '@/utils/message'

export function useToolEditor(
  createForm: () => toolData,
  onSaved: (data: toolData, created: boolean) => void,
) {
  const route = useRoute()
  const { folder, user } = useStore()
  const form = ref(createForm())
  const original = shallowRef<toolData>()
  const visible = ref(false)
  const loading = ref(false)
  const FormRef = ref<FormInstance>()
  const apiType = computed(() => {
    if (route.path.includes('shared')) return 'systemShare'
    if (route.path.includes('resource-management')) return 'systemManage'
    return 'workspace'
  })
  const api = computed(() => loadSharedApi({ type: 'tool', systemType: apiType.value }))
  const permissions = computed(() => permissionMap.tool[apiType.value])
  const isEdit = computed(() => !!form.value.id)
  const canSave = computed(() =>
    form.value.id ? permissions.value.edit(form.value.id) : permissions.value.create(),
  )

  function open(data?: toolData) {
    form.value = { ...createForm(), ...cloneDeep(data) }
    form.value.init_field_list ??= []
    form.value.input_field_list ??= []
    original.value = cloneDeep(form.value)
    FormRef.value?.clearValidate()
    visible.value = true
  }

  async function close() {
    if (loading.value) return
    if (!isEqual(original.value, form.value)) {
      try {
        await MsgConfirm(t('common.tip'), t('views.tool.tip.saveMessage'), {
          confirmButtonText: t('common.confirm'),
        })
      } catch {
        return
      }
    }
    visible.value = false
  }

  async function save(checkContent?: () => boolean) {
    if (loading.value || !canSave.value || !FormRef.value) return
    loading.value = true
    try {
      form.value.name = form.value.name?.trim()
      const valid = await FormRef.value.validate().catch(() => false)
      if (!valid || (checkContent && !checkContent())) return

      const created = !form.value.id
      const { name, desc, code, icon, init_field_list, input_field_list } = form.value
      const definition = { name, desc, code, icon, init_field_list, input_field_list }
      const response = form.value.id
        ? await api.value.putTool(form.value.id, definition)
        : await api.value.postTool({
            ...definition,
            tool_type: form.value.tool_type,
            folder_id:
              form.value.folder_id ||
              folder.currentFolder?.id ||
              user.getWorkspaceId() ||
              'default',
          })
      MsgSuccess(t(created ? 'common.createSuccess' : 'common.editSuccess'))
      visible.value = false
      try {
        await user.profile()
      } finally {
        onSaved(response.data, created)
      }
    } finally {
      loading.value = false
    }
  }

  return { form, visible, loading, isEdit, canSave, FormRef, permissions, api, open, close, save }
}
