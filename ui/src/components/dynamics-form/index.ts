import { defineAsyncComponent, type App, type Component } from 'vue'
import DynamicsForm from './index.vue'
import FormItem from './FormItem.vue'
const components = import.meta.glob<{ default: Component }>([
  './**/*.vue',
  '!./constructor/index.vue',
  '!./FormItem.vue',
  '!./index.vue',
])

const install = (app: App) => {
  Object.keys(components).forEach((key: string) => {
    const commentName: string = key
      .substring(key.lastIndexOf('/') + 1, key.length)
      .replace('.vue', '')
    app.component(commentName, defineAsyncComponent(components[key]))
  })
  app.component('index', DynamicsForm)
  app.component('FormItem', FormItem)
  app.component('DynamicsForm', DynamicsForm)
}
export default { install }
