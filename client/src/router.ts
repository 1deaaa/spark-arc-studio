import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';
import { getUserInfo } from './services/api';
import { getSessionToken } from './services/apiClient';
import { isLocalTauriShell } from './composables/usePlatform';
import LoginPage from './components/user/LoginPage.vue';
import ScriptWriterView from './views/ScriptWriter/ScriptWriterIndex.vue';
import PlayerView from './views/Player/PlayerIndex.vue';
import ShareManagerView from './views/ShareManager/ShareManagerIndex.vue';

import SynopsisView from './views/Synopsis/SynopsisIndex.vue';
import ProductHomeView from './views/ProductHome/ProductHomeIndex.vue';

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

router.beforeEach(async (to, from, next) => {
  if (isLocalTauriShell.value) {
    if (to.name !== 'Login') {
      next('/login');
      return;
    }
    next();
    return;
  }

  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);

  //  optimization: check local token first
  const hasLocalToken = !!getSessionToken();

  // If accessing login page and no local token, skip network validation
  if (to.name === 'Login' && !hasLocalToken) {
    next();
    return;
  }

  let isAuthenticated = false;
  try {
    await getUserInfo();
    isAuthenticated = true;
  } catch (e: unknown) {
    isAuthenticated = false;
  }

  if (requiresAuth && !isAuthenticated) {
    // Save the intended destination before redirecting to login
    if (to.fullPath !== '/') {
      localStorage.setItem('postLoginUrl', to.fullPath);
    }
    next('/login');
  } else if (to.name === 'Login' && isAuthenticated) {
    // If user is logged in and tries to access login page, redirect to home
    next('/');
  } else {
    next();
  }
});

export default router;
