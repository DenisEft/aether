import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // ── Auth routes (no layout) ──────────────────────────────
    {
      path: '/login',
      name: 'login',
      component: () => import('./client/views/LoginView.vue'),
    },
    {
      path: '/signup',
      name: 'signup',
      component: () => import('./client/views/SignupView.vue'),
    },
    {
      path: '/verify',
      name: 'verify',
      component: () => import('./client/views/VerifyView.vue'),
    },
    {
      path: '/invite/:token',
      name: 'accept-invite',
      component: () => import('./client/views/AcceptInviteView.vue'),
    },

    // ── Client workspace (requires auth) ─────────────────────
    {
      path: '/:tenantSlug',
      component: () => import('./client/layouts/ClientLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'workspace',
          component: () => import('./client/views/WorkspaceView.vue'),
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('./client/views/SettingsView.vue'),
        },
        {
          path: 'analytics',
          name: 'analytics',
          component: () => import('./client/views/AnalyticsView.vue'),
        },
        {
          path: 'processes',
          name: 'process-list',
          component: () => import('./client/views/ProcessListView.vue'),
        },
        {
          path: 'processes/:instanceId',
          name: 'process-detail',
          component: () => import('./client/views/ProcessDetailView.vue'),
        },
      ],
    },

    // ── Workspace picker ─────────────────────────────────────
    {
      path: '/workspaces',
      name: 'workspace-picker',
      component: () => import('./client/views/WorkspacePickerView.vue'),
      meta: { requiresAuth: true },
    },

    // ── Admin dashboard (requires superadmin) ────────────────
    {
      path: '/admin',
      component: () => import('./admin/layouts/AdminLayout.vue'),
      meta: { requiresAuth: true, requiresSuperadmin: true },
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('./admin/views/DashboardView.vue'),
        },
        {
          path: 'tenants',
          name: 'admin-tenants',
          component: () => import('./admin/views/TenantsListView.vue'),
        },
        {
          path: 'tenants/:id',
          name: 'admin-tenant-detail',
          component: () => import('./admin/views/TenantDetailView.vue'),
        },
        {
          path: 'subscriptions',
          name: 'admin-subscriptions',
          component: () => import('./admin/views/SubscriptionsView.vue'),
        },
        {
          path: 'drivers',
          name: 'admin-drivers',
          component: () => import('./admin/views/DriversView.vue'),
        },
        {
          path: 'billing',
          name: 'admin-billing',
          component: () => import('./admin/views/BillingView.vue'),
        },
        {
          path: 'audit',
          name: 'admin-audit',
          component: () => import('./admin/views/AuditView.vue'),
        },
      ],
    },

    // ── Catch-all redirect ───────────────────────────────────
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login',
    },
  ],
})

export default router
