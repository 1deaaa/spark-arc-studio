import { createRouter, createWebHashHistory } from 'vue-router';
import { getUserInfo } from './services/api';
import LoginPage from './components/user/LoginPage.vue';
import MainView from './MainView.vue';
import PlayerView from './views/PlayerView.vue';
import ShareManagerView from './views/ShareManagerView.vue';

import SynopsisView from './views/SynopsisView.vue';

const routes = [
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
    component: MainView,
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  let isAuthenticated = false;
  try {
    await getUserInfo();
    isAuthenticated = true;
  } catch (e) {
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