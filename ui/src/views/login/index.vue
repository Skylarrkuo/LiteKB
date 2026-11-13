<template>
  <login-layout>
    <LoginContainer :subTitle="$t('studio.console')">
      <h2 class="mb-24">{{ $t('views.login.title') }}</h2>
      <div>
        <el-form
          class="login-form"
          :rules="rules"
          :model="loginForm"
          ref="loginFormRef"
          @keyup.enter="loginHandle"
          @submit.prevent
        >
          <div class="mb-24">
            <el-form-item prop="username">
              <el-input
                size="large"
                class="input-item"
                v-model="loginForm.username"
                @blur="makeCode(loginForm.username)"
                :placeholder="$t('views.login.loginForm.username.placeholder')"
              >
              </el-input>
            </el-form-item>
          </div>
          <div class="mb-24">
            <el-form-item prop="password">
              <el-input
                type="password"
                size="large"
                class="input-item"
                v-model="loginForm.password"
                :placeholder="$t('views.login.loginForm.password.placeholder')"
                show-password
              >
              </el-input>
            </el-form-item>
          </div>
          <div class="mb-24" v-if="identifyCode">
            <el-form-item prop="captcha">
              <div class="flex-between w-full">
                <el-input
                  size="large"
                  class="input-item"
                  v-model="loginForm.captcha"
                  :placeholder="$t('views.login.loginForm.captcha.placeholder')"
                >
                </el-input>

                <img
                  :src="identifyCode"
                  alt=""
                  height="38"
                  class="ml-8 cursor border border-r-6"
                  @click="makeCode(loginForm.username)"
                />
              </div>
            </el-form-item>
          </div>
        </el-form>

        <el-button
          size="large"
          type="primary"
          class="w-full"
          @click="loginHandle"
          :loading="loading"
          :disabled="!ready"
        >
          {{ $t('views.login.buttons.login') }}
        </el-button>
        <div class="operate-container flex-between mt-12">
          <el-button
            :loading="loading"
            class="forgot-password"
            @click="router.push('/forgot_password')"
            link
            type="primary"
          >
            {{ $t('views.login.forgotPassword') }}?
          </el-button>
        </div>
      </div>
    </LoginContainer>
  </login-layout>
</template>
<script setup lang="ts">
import { onBeforeMount, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import JSEncrypt from 'jsencrypt'
import type { LoginRequest } from '@/api/type/login'
import LoginContainer from '@/layout/login-layout/LoginContainer.vue'
import LoginLayout from '@/layout/login-layout/LoginLayout.vue'
import loginApi from '@/api/user/login'
import { getBrowserLang, t } from '@/locales'
import useStore from '@/stores'

const router = useRouter()
const { login, user } = useStore()
const { locale } = useI18n({ useScope: 'global' })
const loading = ref(false)
const ready = ref(false)
const identifyCode = ref('')
const loginFormRef = ref<FormInstance>()
const loginForm = ref<LoginRequest>({
  username: '',
  password: '',
  captcha: '',
})

const rules = ref<FormRules<LoginRequest>>({
  username: [
    {
      required: true,
      message: t('views.login.loginForm.username.requiredMessage'),
      trigger: 'blur',
    },
  ],
  password: [
    {
      required: true,
      message: t('views.login.loginForm.password.requiredMessage'),
      trigger: 'blur',
    },
  ],
  captcha: [
    {
      required: false,
      message: t('views.login.loginForm.captcha.requiredMessage'),
      trigger: 'blur',
    },
  ],
})

async function makeCode(username?: string) {
  const response = await loginApi.getCaptcha(username)
  identifyCode.value = response.data?.captcha || ''
}

async function loginHandle() {
  if (!ready.value || loading.value || !await loginFormRef.value?.validate().catch(() => false)) return
  loading.value = true
  try {
    const Cipher = (JSEncrypt as any).default || JSEncrypt
    const cipher = new Cipher()
    cipher.setPublicKey(user.rsaKey)
    await login.asyncLogin({
      encryptedData: cipher.encrypt(JSON.stringify(loginForm.value)),
      username: loginForm.value.username,
    })
    locale.value = localStorage.getItem('MaxKB-locale') || getBrowserLang() || 'en-US'
    await router.replace('/application')
  } catch {
    await makeCode(loginForm.value.username)
  } finally {
    loading.value = false
  }
}

onBeforeMount(async () => {
  await user.asyncGetProfile()
  ready.value = true
})
</script>
