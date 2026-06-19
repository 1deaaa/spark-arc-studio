import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';
import { getSessionToken } from './services/apiClient';
import { isLocalTauriShell } from './composables/usePlatform';
const LoginPage = () => import('./components/user/LoginPage.vue');
const ScriptWriterView = () => import('./views/ScriptWriter/ScriptWriterIndex.vue');
const PlayerView = () => import('./views/Player/PlayerIndex.vue');
const ShareManagerView = () => import('./views/ShareManager/ShareManagerIndex.vue');
const SynopsisView = () => import('./views/Synopsis/SynopsisIndex.vue');
const ProductHomeView = () => import('./views/ProductHome/ProductHomeIndex.vue');

const routes: RouteRecordRaw[] = [
  {
    path: '/index',
    name: 'ProductHome',
    component: ProductHomeView,
    meta: { requiresAuth: false },
  },
  {
    path: '/synopsis',
    name: 'Synopsis',
    component: SynopsisView,
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: LoginPage,
  },
  {
    path: '/play/:shareId',
    name: 'Player',
    component: PlayerView,
    meta: { requiresAuth: false },
  },
  {
    path: '/play/v/:shareId',
    name: 'VersionPlayer',
    component: PlayerView,
    meta: { requiresAuth: false },
  },
  {
    path: '/shares',
    name: 'ShareManager',
    component: ShareManagerView,
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'Editor',
    component: ScriptWriterView,
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to) => {
  if (isLocalTauriShell.value) {
    if (to.name !== 'Login') {
      return '/login';
    }
    return true;
  }

  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);

  // 对于不需要认证的路由（如公开分享页面），直接放行，跳过认证检查
  // 这样可以避免未登录用户访问公开分享时被强制跳转到登录页
  if (!requiresAuth && to.name !== 'Login') {
    return true;
  }

  // 路由守卫只做本地 token 快速判断，真实过期由 fetchWithAuth 的 401 处理统一收口。
  // 自动写作等后台任务繁忙时，首屏不能被 /api/user/info 阻塞，否则 router-view 会迟迟不放行。
  const hasLocalToken = !!getSessionToken();

  if (to.name === 'Login' && !hasLocalToken) {
    return true;
  }
  if (requiresAuth && !hasLocalToken) {
    // 跳转登录前记录原目标，登录后可回到用户本来想去的位置。
    if (to.fullPath !== '/') {
      localStorage.setItem('postLoginUrl', to.fullPath);
    }
    return '/login';
  }
  if (to.name === 'Login' && hasLocalToken) {
    return '/';
  }
  return true;
});

export default router;
