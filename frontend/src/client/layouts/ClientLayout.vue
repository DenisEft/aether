<template>
  <div
    class="client-layout"
    :class="{ 'sidebar-collapsed': sidebarCollapsed }"
  >
    <!-- Left Sidebar — 240px (collapsible to 56px) -->
    <aside
      class="sidebar"
      @mouseenter="sidebarCollapsed = false"
      @mouseleave="sidebarCollapsed = true"
    >
      <div class="sidebar-header">
        <div
          class="org-switcher"
          title="Switch workspace"
          @click="$router.push('/workspaces')"
        >
          <div class="org-avatar">
            {{ orgInitials }}
          </div>
          <span
            v-if="!sidebarCollapsed"
            class="org-name"
          >{{ tenantName }}</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <router-link
          :to="`/${tenantSlug}`"
          class="nav-item"
          :class="{ active: route.name === 'workspace' || !route.name }"
          title="Inbox"
        >
          <span class="nav-icon">📥</span>
          <span
            v-if="!sidebarCollapsed"
            class="nav-label"
          >Inbox</span>
          <span
            v-if="!sidebarCollapsed && unreadCount > 0"
            class="nav-badge"
          >{{ unreadCount }}</span>
        </router-link>
        <router-link
          :to="`/${tenantSlug}/settings`"
          class="nav-item"
          :class="{ active: route.name === 'settings' }"
          title="Settings"
        >
          <span class="nav-icon">⚙️</span>
          <span
            v-if="!sidebarCollapsed"
            class="nav-label"
          >Settings</span>
        </router-link>
        <router-link
          :to="`/${tenantSlug}/processes`"
          class="nav-item"
          :class="{ active: route.name === 'process-list' || route.name === 'process-detail' }"
          title="Processes"
        >
          <span class="nav-icon">⚙️</span>
          <span
            v-if="!sidebarCollapsed"
            class="nav-label"
          >Processes</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <div
          v-if="!sidebarCollapsed"
          class="user-info"
        >
          <div class="user-avatar">
            {{ userInitials }}
          </div>
          <span class="user-name">{{ userName }}</span>
        </div>
        <div
          v-else
          class="user-info-collapsed"
        >
          <div
            class="user-avatar"
            :title="userName"
          >
            {{ userInitials }}
          </div>
        </div>
      </div>
    </aside>

    <!-- Middle Panel — ConversationList (320px) -->
    <section
      class="panel-middle"
      :class="{ hidden: mobilePanel !== 'list' && mobilePanel !== 'all' }"
    >
      <router-view v-if="hasChildRoute" />
      <slot v-else />
    </section>

    <!-- Right Panel — Chat/Detail (flex-1) -->
    <section
      class="panel-right"
      :class="{ hidden: mobilePanel !== 'chat' && mobilePanel !== 'all' }"
    >
      <!-- Child views render here via router, or we render directly -->
      <router-view v-if="!hasChildRoute" />
    </section>

    <!-- Keyboard Hint Bar -->
    <div class="kbd-hints">
      <span><kbd>↑↓</kbd> Navigate</span>
      <span><kbd>Enter</kbd> Open</span>
      <span><kbd>Esc</kbd> Back</span>
      <span><kbd>Ctrl+K</kbd> Search</span>
    </div>

    <!-- Mobile Nav Tabs -->
    <nav
      v-if="isMobile"
      class="mobile-nav"
    >
      <button
        :class="{ active: mobilePanel === 'list' }"
        @click="mobilePanel = 'list'"
      >
        📋 List
      </button>
      <button
        :class="{ active: mobilePanel === 'chat' }"
        @click="mobilePanel = 'chat'"
      >
        💬 Chat
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTenant } from '../../shared/composables/useTenant'
import { useAuth } from '../../shared/composables/useAuth'

const route = useRoute()
const { currentTenant, loadTenant } = useTenant()
const { currentUser } = useAuth()

const sidebarCollapsed = ref(false)
const hoverTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const tenantSlug = computed(() => route.params.tenantSlug as string)
const tenantName = computed(() => currentTenant.value?.name || tenantSlug.value || 'Aether')
const orgInitials = computed(() => (tenantName.value || 'AE').substring(0, 2).toUpperCase())
const userName = computed(() => currentUser.value?.display_name || currentUser.value?.email || 'User')
const userInitials = computed(() => (userName.value || 'U').substring(0, 2).toUpperCase())
const unreadCount = ref(0)

const isMobile = ref(false)
const mobilePanel = ref<'list' | 'chat' | 'all'>('all')

const hasChildRoute = computed(() => {
  return route.matched.length > 1
})

function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) mobilePanel.value = 'all'
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  if (tenantSlug.value) {
    await loadTenant(tenantSlug.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.client-layout {
  display: flex;
  height: 100vh;
  background: #f8f9fa;
  position: relative;
}

/* ── Left Sidebar ── */
.sidebar {
  width: 240px;
  min-width: 240px;
  background: #fff;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease, min-width 0.2s ease;
  z-index: 10;
}
.sidebar-collapsed .sidebar {
  width: 56px;
  min-width: 56px;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid #e8eaed;
}
.org-switcher {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  border-radius: 8px;
  padding: 6px 8px;
  transition: background 0.15s;
}
.org-switcher:hover {
  background: #f1f3f4;
}
.org-avatar {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #1a73e8;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.org-name {
  font-size: 14px;
  font-weight: 600;
  color: #202124;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Sidebar Nav ── */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  overflow-y: auto;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  color: #5f6368;
  font-weight: 500;
  font-size: 13px;
  text-decoration: none;
  transition: all 0.15s;
  white-space: nowrap;
  position: relative;
}
.nav-item:hover {
  background: #f1f3f4;
}
.nav-item.active {
  background: #e8f0fe;
  color: #1a73e8;
}
.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}
.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-badge {
  margin-left: auto;
  background: #1a73e8;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

/* ── Sidebar Footer ── */
.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #e8eaed;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-info-collapsed {
  display: flex;
  justify-content: center;
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #5f6368;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-name {
  font-size: 12px;
  color: #3c4043;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Middle Panel ── */
.panel-middle {
  width: 320px;
  min-width: 320px;
  border-right: 1px solid #e0e0e0;
  background: #fff;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* ── Right Panel ── */
.panel-right {
  flex: 1;
  min-width: 0;
  background: #fff;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* ── Keyboard Hints Bar ── */
.kbd-hints {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 24px;
  background: #f1f3f4;
  border-top: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-size: 11px;
  color: #80868b;
  z-index: 50;
}
.kbd-hints kbd {
  display: inline-block;
  padding: 0 4px;
  font-size: 10px;
  font-family: inherit;
  background: #fff;
  border: 1px solid #dadce0;
  border-radius: 3px;
  color: #3c4043;
}

/* ── Mobile Nav ── */
.mobile-nav {
  display: none;
  position: fixed;
  bottom: 24px;
  left: 0;
  right: 0;
  height: 48px;
  background: #fff;
  border-top: 1px solid #e0e0e0;
  z-index: 49;
}
.mobile-nav button {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #5f6368;
  cursor: pointer;
  font-weight: 500;
}
.mobile-nav button.active {
  color: #1a73e8;
  border-bottom: 2px solid #1a73e8;
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .sidebar { width: 56px; min-width: 56px; }
  .panel-middle { width: 280px; min-width: 280px; }
}

@media (max-width: 767px) {
  .client-layout { flex-direction: column; }
  .sidebar { display: none; }
  .panel-middle {
    width: 100%;
    min-width: 100%;
    flex: 1;
  }
  .panel-middle.hidden { display: none; }
  .panel-right {
    width: 100%;
    min-width: 100%;
    flex: 1;
  }
  .panel-right.hidden { display: none; }
  .mobile-nav { display: flex; }
  .kbd-hints { display: none; }
}
</style>
