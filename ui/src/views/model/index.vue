<template>
  <LayoutContainer showCollapse class="model-manage" :navigation-label="$t('views.model.provider')">
    <template #left>
      <h3 class="provider-heading">{{ $t('views.model.provider') }}</h3>
      <ProviderComponent
        :data="provider_list"
        @click="clickListHandle"
        :loading="loading"
        :showShared="false"
        :active="active_provider"
      />
    </template>
    <ContentContainer :aria-busy="list_model_loading">
      <template #header>
        <div class="model-heading">
          <h2>{{ active_provider?.name || $t('views.model.modelType.allModel') }}</h2>
          <span v-if="!loading && !list_model_loading" class="model-count">{{
            model_list.length
          }}</span>
        </div>
      </template>
      <template #search>
        <div class="model-actions flex">
          <div class="complex-search">
            <el-select
              class="complex-search__left"
              v-model="search_type"
              :aria-label="$t('common.search')"
              @change="search_type_change"
            >
              <el-option :label="$t('common.creator')" value="create_user" />
              <el-option :label="$t('views.model.modelForm.model_type.label')" value="model_type" />
              <el-option :label="$t('views.model.modelForm.modeName.label')" value="name" />
            </el-select>
            <el-input
              v-if="search_type === 'name'"
              v-model="model_search_form.name"
              @change="list_model"
              :placeholder="$t('common.searchBar.placeholder')"
              :aria-label="$t('common.name')"
              clearable
            />
            <el-select
              v-else-if="search_type === 'create_user'"
              v-model="model_search_form.create_user"
              @change="list_model"
              filterable
              clearable
              remote
              :remote-method="getUserList"
              :aria-label="$t('common.creator')"
            >
              <el-option v-for="u in user_options" :key="u.id" :value="u.id" :label="u.nick_name" />
            </el-select>
            <el-select
              v-else-if="search_type === 'model_type'"
              v-model="model_search_form.model_type"
              clearable
              @change="list_model"
              :aria-label="$t('views.model.modelForm.model_type.label')"
            >
              <template v-for="item in modelTypeList" :key="item.value">
                <el-option :label="item.text" :value="item.value" />
              </template>
            </el-select>
          </div>
          <el-button
            v-if="!isShared && permissionPrecise.create()"
            type="primary"
            @click="openCreateModel(active_provider)"
          >
            <el-icon aria-hidden="true"><Plus /></el-icon
            ><span>{{ $t('views.model.addModel') }}</span>
          </el-button>
        </div>
      </template>

      <div v-if="model_list.length" class="model-grid studio-result-enter">
        <ModelCard
          v-for="model in model_list"
          :key="model.id"
          @change="list_model"
          :updateModelById="updateModelById"
          :model="model"
          :provider_list="provider_list"
          :isShared="isShared"
          :isSystemShare="isSystemShare"
          :apiType="apiType"
        />
      </div>
      <ListPlaceholder v-else-if="loading || list_model_loading" />
      <div v-else-if="!loading && !list_model_loading" class="model-empty">
        <span class="empty-icon" aria-hidden="true"
          ><el-icon><Cpu /></el-icon
        ></span>
        <h3>{{ hasFilter ? $t('studio.noMatchingModels') : $t('studio.noModels') }}</h3>
      </div>
    </ContentContainer>

    <CreateModelDialog
      ref="createModelRef"
      @submit="list_model"
      @change="openCreateModel($event)"
      v-if="!isShared"
    ></CreateModelDialog>

    <SelectProviderDialog
      ref="selectProviderRef"
      @change="(provider, modelType) => openCreateModel(provider, modelType)"
      v-if="!isShared"
    ></SelectProviderDialog>
  </LayoutContainer>
</template>

<script lang="ts" setup>
import ListPlaceholder from '@/components/ListPlaceholder.vue'
import { onMounted, ref, computed } from 'vue'
import type { Provider, Model } from '@/api/type/model'
import ModelCard from '@/views/model/component/ModelCard.vue'
import ProviderComponent from '@/views/model/component/Provider.vue'
import { modelTypeList, allObj } from '@/views/model/component/data'
import CreateModelDialog from '@/views/model/component/CreateModelDialog.vue'
import SelectProviderDialog from '@/views/model/component/SelectProviderDialog.vue'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import useStore from '@/stores'
import { useRoute } from 'vue-router'
import permissionMap from '@/permission'

const route = useRoute()
const { model, user } = useStore()
const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const permissionPrecise = computed(() => {
  return permissionMap['model'][apiType.value]
})
const isSystemShare = computed(() => {
  return apiType.value === 'systemShare'
})
const loading = ref<boolean>(false)

const active_provider = ref<Provider>()
const search_type = ref('name')
const model_search_form = ref<{
  name: string
  create_user: string
  model_type: string
}>({
  name: '',
  create_user: '',
  model_type: '',
})
const user_options = ref<any[]>([])
const list_model_loading = ref<boolean>(false)
const provider_list = ref<Array<Provider>>([])

const model_list = ref<Array<Model>>([])

const isShared = computed(() => {
  return active_provider.value && active_provider.value.provider === 'share'
})
const updateModelById = (model_id: string, model: Model) => {
  model_list.value
    .filter((m) => m.id == model_id)
    .forEach((m) => {
      m.status = model.status
    })
}
const hasFilter = computed(() =>
  Boolean(active_provider.value?.provider || Object.values(model_search_form.value).some(Boolean)),
)
const createModelRef = ref<InstanceType<typeof CreateModelDialog>>()
const selectProviderRef = ref<InstanceType<typeof SelectProviderDialog>>()

const clickListHandle = (item: Provider) => {
  active_provider.value = item
  list_model()
}

const openCreateModel = (provider?: Provider, model_type?: string) => {
  if (provider && provider.provider) {
    createModelRef.value?.open(provider, model_type)
  } else {
    selectProviderRef.value?.open()
  }
}

function getUserList(query: string) {
  let workspaceId = user.getWorkspaceId()
  if (isSystemShare.value) {
    workspaceId = ''
  }
  const actualWorkspaceId = workspaceId || (query ? { nick_name: query } : '')
  const actualQuery = workspaceId ? (query ? { nick_name: query } : '') : undefined

  loadSharedApi({ type: 'workspace', isShared: isShared.value, systemType: apiType.value })
    .getAllMemberList(actualWorkspaceId, actualQuery, loading)
    .then((res: any) => {
      user_options.value = res.data
    })
}

let listRequest = 0
const list_model = async () => {
  const request = ++listRequest
  list_model_loading.value = true
  const params =
    active_provider.value?.provider && active_provider.value?.provider !== 'share'
      ? { provider: active_provider.value.provider }
      : {}
  try {
    const api = loadSharedApi({
      type: 'model',
      isShared: isShared.value,
      systemType: apiType.value,
    })
    const { data } = await api.getModelList({ ...model_search_form.value, ...params })
    if (request === listRequest) model_list.value = data
  } finally {
    if (request === listRequest) list_model_loading.value = false
  }
}

const search_type_change = () => {
  model_search_form.value = { name: '', create_user: '', model_type: '' }
  list_model()
}

onMounted(() => {
  model.asyncGetProvider(loading).then((ok: any) => {
    provider_list.value = [allObj, ...ok.data]
  })
  active_provider.value = allObj
  list_model()
})
</script>

<style lang="scss" scoped>
.model-manage {
  .provider-heading {
    padding: 20px 20px 14px;
    font-size: 15px;
    font-weight: 650;
  }
  :deep(.layout-container__left_content) {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .model-heading,
  .model-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .model-count {
    border-radius: 20px;
    background: #e1eae5;
    color: #39544a;
    font-size: 12px;
    line-height: 22px;
    padding: 0 8px;
    font-variant-numeric: tabular-nums;
  }
  .complex-search {
    display: grid;
    grid-template-columns: 116px minmax(130px, 195px);
    background: white;
  }
  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 270px), 1fr));
    gap: 15px;
  }
  .model-empty {
    display: grid;
    place-content: center;
    justify-items: center;
    gap: 12px;
    min-height: clamp(240px, 43vh, 430px);
    padding: 16px;
    background: white;
    border: 1px solid var(--studio-hairline);
    border-radius: 16px;
    h3 {
      color: var(--el-text-color-regular);
      font-size: 16px;
      font-weight: 550;
    }
  }
  .empty-icon {
    color: var(--studio-ink);
    background: var(--studio-selection);
    width: 54px;
    height: 54px;
    display: grid;
    place-items: center;
    font-size: 27px;
    border-radius: 16px;
  }
  @media (max-width: 760px) {
    .model-actions {
      flex-wrap: wrap;
    }
    .complex-search {
      flex: 1 1 200px;
      grid-template-columns: minmax(70px, 0.8fr) minmax(85px, 1.2fr);
    }
    :deep(.layout-container__left_content) {
      max-height: 35dvh;
    }
    .provider-heading {
      display: none;
    }
  }
}
</style>
