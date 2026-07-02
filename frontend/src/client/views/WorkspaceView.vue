<template>
  <div class="workspace" @keydown="handleKeydown" tabindex="0" ref="workspaceEl">
    <!-- ── LEFT SIDEBAR ── -->
    <aside class="ws-sidebar">
      <!-- Channel List -->
      <div class="ws-section">
        <div class="ws-section-title">Channels</div>
        <div v-if="store.channels.length === 0 && !channelsLoading" class="ws-empty-mini">
          <span class="empty-icon">📡</span>
          <span class="empty-text">No channels</span>
        </div>
        <div
          v-for="channel in store.channels"
          :key="channel.id"
          class="channel-item"
          :class="{ active: activeChannel === channel.id }"
          @click="activeChannel = activeChannel === channel.id ? null : channel.id"
        >
          <span class="channel-icon">{{ channelIcon(channel.channel_type) }}</span>
          <span class="channel-name">{{ channel.display_name }}</span>
          <span class="channel-dot" :class="{ online: channel.is_active }" />
        </div>
      </div>

      <!-- Organisation Info -->
      <div class="ws-section">
        <div class="ws-section-title">Organisation</div>
        <div class="org-info">
          <span class="org-members">👥 {{ memberCount }} members</span>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="ws-section">
        <router-link :to="`/${tenantSlug}/settings`" class="quick-action">
          <span>⚙️</span> Settings
        </router-link>
      </div>
    </aside>

    <!-- ── MIDDLE PANEL: ConversationList ── -->
    <section class="ws-conversations">
      <!-- Search -->
      <div class="conv-search">
        <span class="search-icon">🔍</span>
        <input
          v-model="searchQuery"
          placeholder="Search conversations..."
          class="search-input"
          @keydown.escape="searchQuery = ''"
        />
      </div>

      <!-- Filter Tabs -->
      <div class="conv-filters">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          :class="{ active: activeFilter === tab.value }"
          @click="activeFilter = tab.value"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Loading Skeleton -->
      <div v-if="loading" class="conv-loading">
        <div v-for="i in 5" :key="i" class="conv-skeleton">
          <div class="skel-avatar" />
          <div class="skel-lines">
            <div class="skel-line w-60" />
            <div class="skel-line w-80" />
            <div class="skel-line w-40" />
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredConversations.length === 0" class="conv-empty">
        <div class="empty-illustration">💬</div>
        <h3>No conversations yet</h3>
        <p v-if="store.channels.length === 0">
          Connect a channel to start receiving messages from your customers.
        </p>
        <p v-else>
          All caught up! New conversations will appear here.
        </p>
        <router-link v-if="store.channels.length === 0" :to="`/${tenantSlug}/settings`" class="cta-link">
          ⚡ Connect a channel
        </router-link>
      </div>

      <!-- Conversation Cards -->
      <div v-else class="conv-list" ref="convListEl">
        <div
          v-for="(conv, idx) in filteredConversations"
          :key="conv.id"
          class="conv-card"
          :class="{
            active: store.activeConversationId === conv.id,
            unread: conv.unread_count > 0,
          }"
          :data-index="idx"
          @click="selectConversation(conv.id)"
          @keydown.enter="selectConversation(conv.id)"
        >
          <div class="conv-avatar" :style="{ background: avatarColor(conv.subject) }">
            {{ (conv.subject || '?')[0].toUpperCase() }}
          </div>
          <div class="conv-body">
            <div class="conv-header">
              <span class="conv-subject">{{ conv.subject || 'No subject' }}</span>
              <span class="conv-time">{{ formatTime(conv.last_message_at) }}</span>
            </div>
            <div class="conv-preview">{{ conv.last_message_preview || 'No messages' }}</div>
            <div class="conv-meta">
              <span class="conv-channel-badge" v-if="channelName(conv.channel_id)">
                {{ channelIconForConv(conv.channel_id) }} {{ channelName(conv.channel_id) }}
              </span>
              <span v-if="conv.unread_count > 0" class="conv-unread-dot" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── RIGHT PANEL: ChatWindow ── -->
    <section class="ws-chat">
      <!-- No conversation selected -->
      <div v-if="!store.activeConversationId" class="chat-empty">
        <div class="chat-empty-icon">💬</div>
        <h2>Select a conversation</h2>
        <p>Choose a conversation from the list to start chatting</p>
      </div>

      <!-- Active conversation -->
      <template v-else>
        <!-- Chat Header -->
        <div class="chat-header">
          <div class="chat-header-left">
            <button class="btn-back" @click="store.selectConversation(null)" title="Back (Esc)">
              ←
            </button>
            <div class="chat-avatar" :style="{ background: avatarColor(activeConversation?.subject || '') }">
              {{ (activeConversation?.subject || '?')[0].toUpperCase() }}
            </div>
            <div class="chat-header-info">
              <div class="chat-header-name">{{ activeConversation?.subject || 'No subject' }}</div>
              <div class="chat-header-channel" v-if="activeConversation">
                {{ channelIconForConv(activeConversation.channel_id) }}
                {{ channelName(activeConversation.channel_id) }}
                <span class="status-dot" :class="{ active: wsConnected }" />
              </div>
            </div>
          </div>
          <div class="chat-header-actions">
            <button class="btn-icon" title="Conversation info">ℹ️</button>
          </div>
        </div>

        <!-- Messages -->
        <div class="chat-messages" ref="messagesEl">
          <div v-if="messagesLoading" class="messages-loading">
            <span class="spinner" /> Loading messages...
          </div>
          <div
            v-for="msg in store.messages"
            :key="msg.id"
            class="chat-bubble"
            :class="msg.role"
          >
            <div class="bubble-content">{{ msg.content }}</div>
            <div class="bubble-time">{{ formatMessageTime(msg.created_at) }}</div>
          </div>
          <div v-if="store.messages.length === 0 && !messagesLoading" class="messages-empty">
            No messages yet. Say hello!
          </div>
        </div>

        <!-- Chat Composer -->
        <div class="chat-composer">
          <textarea
            v-model="composerText"
            class="composer-input"
            placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
            rows="1"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoResize"
            ref="composerEl"
          />
          <button
            class="btn-send"
            :disabled="!composerText.trim()"
            @click="sendMessage"
            title="Send (Enter)"
          >
            ▶
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '../../stores/workspace'
import { useWebSocket } from '../../shared/composables/useWebSocket'
import type { ChannelType } from '../../shared/types/common'

const route = useRoute()
const tenantSlug = computed(() => route.params.tenantSlug as string)
const store = useWorkspaceStore()

// ── WebSocket ──
const { connected: wsConnected, connect: wsConnect } = useWebSocket(tenantSlug.value)

// ── State ──
const loading = computed(() => store.loading)
const messagesLoading = ref(false)
const searchQuery = ref('')
const activeFilter = ref<'all' | 'active' | 'closed'>('all')
const activeChannel = ref<string | null>(null)
const composerText = ref('')

// ── Refs ──
const workspaceEl = ref<HTMLElement | null>(null)
const convListEl = ref<HTMLElement | null>(null)
const messagesEl = ref<HTMLElement | null>(null)
const composerEl = ref<HTMLElement | null>(null)
const channelsLoading = ref(false)

// ── Filter tabs ──
const filterTabs = computed(() => [
  { label: 'All', value: 'all', count: allCount.value },
  { label: 'Active', value: 'active', count: activeCount.value },
  { label: 'Closed', value: 'closed', count: closedCount.value },
])

const allCount = computed(() => channelFilteredConversations.value.length)
const activeCount = computed(() => channelFilteredConversations.value.filter(c => c.status === 'active').length)
const closedCount = computed(() => channelFilteredConversations.value.filter(c => c.status === 'closed').length)

// ── Filtered conversations ──
const channelFilteredConversations = computed(() => {
  let convs = store.conversations
  if (activeChannel.value) {
    convs = convs.filter(c => c.channel_id === activeChannel.value)
  }
  return convs
})

const filteredConversations = computed(() => {
  let convs = channelFilteredConversations.value

  // Status filter
  if (activeFilter.value !== 'all') {
    convs = convs.filter(c => c.status === activeFilter.value)
  }

  // Search
  const q = searchQuery.value.toLowerCase().trim()
  if (q) {
    convs = convs.filter(
      c =>
        (c.subject || '').toLowerCase().includes(q) ||
        (c.last_message_preview || '').toLowerCase().includes(q)
    )
  }

  return convs
})

const activeConversation = computed(() =>
  store.conversations.find(c => c.id === store.activeConversationId) || null
)

// ── Mock member count (TODO: from API) ──
const memberCount = ref(1)

// ── Icon helpers ──
function channelIcon(type: ChannelType): string {
  const map: Record<ChannelType, string> = {
    telegram: '📱',
    whatsapp: '💬',
    email: '✉️',
    web_widget: '🌐',
    sms: '📩',
  }
  return map[type] || '📡'
}

function channelIconForConv(channelId: string): string {
  const ch = store.channels.find(c => c.id === channelId)
  return ch ? channelIcon(ch.channel_type) : '📡'
}

function channelName(channelId: string): string {
  const ch = store.channels.find(c => c.id === channelId)
  return ch?.display_name || ''
}

// ── Time formatting ──
function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatMessageTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

// ── Avatar color ──
function avatarColor(name: string): string {
  const colors = ['#1a73e8', '#34a853', '#ea4335', '#fbbc04', '#8e24aa', '#00acc1', '#d81b60']
  let hash = 0
  for (let i = 0; i < (name || '?').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

// ── Selection ──
async function selectConversation(id: string) {
  store.selectConversation(id)
  messagesLoading.value = true
  try {
    await store.loadMessages(id)
  } finally {
    messagesLoading.value = false
    await nextTick()
    scrollMessagesBottom()
    if (isMobile()) {
      mobilePanel.value = 'chat'
    }
  }
}

// ── Send message ──
async function sendMessage() {
  const text = composerText.value.trim()
  if (!text || !store.activeConversationId) return

  await store.sendMessage(store.activeConversationId, text)
  composerText.value = ''
  await nextTick()
  scrollMessagesBottom()
  if (composerEl.value) {
    composerEl.value.style.height = 'auto'
  }
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

// ── Scroll ──
function scrollMessagesBottom() {
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

// ── Keyboard navigation ──
function handleKeydown(e: KeyboardEvent) {
  // Ctrl+K: focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    const input = document.querySelector('.search-input') as HTMLInputElement
    input?.focus()
    return
  }

  // Esc: go back / deselect conversation
  if (e.key === 'Escape') {
    store.selectConversation(null)
    workspaceEl.value?.focus()
    return
  }

  // Arrow navigation in conversation list
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    navigateConversationList(e.key === 'ArrowDown' ? 1 : -1)
    return
  }
}

let selectedConvIndex = -1
function navigateConversationList(dir: number) {
  const items = filteredConversations.value
  if (items.length === 0) return
  selectedConvIndex = Math.min(Math.max(selectedConvIndex + dir, 0), items.length - 1)
  const conv = items[selectedConvIndex]
  if (conv) {
    selectConversation(conv.id)
  }
  // Scroll item into view
  nextTick(() => {
    const el = document.querySelector('.conv-card.active') as HTMLElement | null
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

// ── Mobile detection ──
const mobilePanel = ref<'list' | 'chat'>('list')
function isMobile() {
  return window.innerWidth < 768
}

// ── Lifecycle ──
onMounted(async () => {
  // Load data
  channelsLoading.value = true
  await store.loadChannels()
  channelsLoading.value = false
  await store.loadConversations()

  // Connect WebSocket
  wsConnect()

  // Focus for keyboard nav
  workspaceEl.value?.focus()
})

// Watch for new WebSocket messages — could trigger conversation refresh
watch(
  () => store.activeConversationId,
  (newId) => {
    if (newId) {
      nextTick(() => scrollMessagesBottom())
    }
  }
)
</script>

<style scoped>
.workspace {
  display: flex;
  height: calc(100vh - 24px); /* account for kbd hints bar */
  outline: none;
}

/* ── Left Sidebar ── */
.ws-sidebar {
  width: 200px;
  min-width: 200px;
  background: #f8f9fa;
  border-right: 1px solid #e0e0e0;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}
.ws-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #80868b;
  padding: 0 8px;
  margin-bottom: 4px;
}
.channel-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #3c4043;
  transition: background 0.15s;
}
.channel-item:hover {
  background: #e8eaed;
}
.channel-item.active {
  background: #e8f0fe;
  color: #1a73e8;
}
.channel-icon {
  font-size: 16px;
}
.channel-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.channel-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dadce0;
  flex-shrink: 0;
}
.channel-dot.online {
  background: #34a853;
}
.ws-empty-mini {
  padding: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #80868b;
}
.empty-icon { font-size: 14px; }
.empty-text { font-style: italic; }
.org-info {
  padding: 0 8px;
}
.org-members {
  font-size: 12px;
  color: #5f6368;
}
.quick-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  color: #3c4043;
  text-decoration: none;
  transition: background 0.15s;
}
.quick-action:hover {
  background: #e8eaed;
}

/* ── Conversation List ── */
.ws-conversations {
  width: 320px;
  min-width: 320px;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.conv-search {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #e8eaed;
  gap: 8px;
}
.search-icon {
  font-size: 14px;
  color: #80868b;
  flex-shrink: 0;
}
.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 13px;
  color: #202124;
  background: transparent;
}
.search-input::placeholder {
  color: #80868b;
}

.conv-filters {
  display: flex;
  padding: 6px 12px;
  border-bottom: 1px solid #e8eaed;
  gap: 4px;
}
.conv-filters button {
  padding: 4px 12px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  color: #5f6368;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.15s;
}
.conv-filters button:hover {
  background: #f1f3f4;
}
.conv-filters button.active {
  background: #e8f0fe;
  color: #1a73e8;
}
.tab-count {
  margin-left: 4px;
  font-size: 11px;
  color: #80868b;
}

/* Loading Skeleton */
.conv-loading {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.conv-skeleton {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
}
.skel-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e8eaed;
  flex-shrink: 0;
}
.skel-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.skel-line {
  height: 8px;
  border-radius: 4px;
  background: #e8eaed;
}
.w-60 { width: 60%; }
.w-80 { width: 80%; }
.w-40 { width: 40%; }

/* Empty State */
.conv-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  text-align: center;
}
.empty-illustration {
  font-size: 48px;
  margin-bottom: 12px;
}
.conv-empty h3 {
  font-size: 16px;
  font-weight: 600;
  color: #202124;
  margin-bottom: 4px;
}
.conv-empty p {
  font-size: 13px;
  color: #5f6368;
  max-width: 240px;
  line-height: 1.4;
}
.cta-link {
  margin-top: 12px;
  color: #1a73e8;
  font-weight: 500;
  font-size: 13px;
  text-decoration: none;
}
.cta-link:hover {
  text-decoration: underline;
}

/* Conversation Cards */
.conv-list {
  flex: 1;
  overflow-y: auto;
}
.conv-card {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f3f4;
  cursor: pointer;
  transition: background 0.1s;
}
.conv-card:hover {
  background: #f8f9fa;
}
.conv-card.active {
  background: #e8f0fe;
}
.conv-card.unread {
  background: #f8fbff;
}
.conv-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.conv-body {
  flex: 1;
  min-width: 0;
}
.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.conv-subject {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}
.conv-time {
  font-size: 11px;
  color: #80868b;
  flex-shrink: 0;
}
.conv-preview {
  font-size: 12px;
  color: #5f6368;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}
.conv-channel-badge {
  font-size: 11px;
  color: #80868b;
}
.conv-unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1a73e8;
  margin-left: auto;
}

/* ── Chat Window ── */
.ws-chat {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}

/* Empty chat */
.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #5f6368;
}
.chat-empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}
.chat-empty h2 {
  font-size: 18px;
  font-weight: 600;
  color: #202124;
  margin-bottom: 4px;
}
.chat-empty p {
  font-size: 13px;
}

/* Chat Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #e8eaed;
  min-height: 56px;
}
.chat-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.btn-back {
  display: none;
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #5f6368;
  padding: 4px;
  border-radius: 4px;
}
.btn-back:hover {
  background: #f1f3f4;
}
.chat-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chat-header-name {
  font-size: 14px;
  font-weight: 600;
  color: #202124;
}
.chat-header-channel {
  font-size: 11px;
  color: #80868b;
}
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #dadce0;
  margin-left: 4px;
}
.status-dot.active {
  background: #34a853;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #5f6368;
  padding: 6px;
  border-radius: 6px;
}
.btn-icon:hover {
  background: #f1f3f4;
}

/* Messages Area */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.messages-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: #80868b;
  font-size: 13px;
}
.messages-empty {
  text-align: center;
  color: #80868b;
  font-size: 13px;
  padding: 24px;
}
.chat-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  position: relative;
}
.chat-bubble.user {
  align-self: flex-end;
  background: #e8f0fe;
  color: #202124;
  border-bottom-right-radius: 4px;
}
.chat-bubble.assistant {
  align-self: flex-start;
  background: #f1f3f4;
  color: #202124;
  border-bottom-left-radius: 4px;
}
.chat-bubble.system {
  align-self: center;
  background: #fef7e0;
  color: #5f6368;
  font-size: 11px;
  padding: 6px 12px;
  max-width: 90%;
}
.bubble-time {
  font-size: 10px;
  color: #80868b;
  margin-top: 4px;
  text-align: right;
}

/* Chat Composer */
.chat-composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e8eaed;
  background: #fff;
}
.composer-input {
  flex: 1;
  border: 1px solid #dadce0;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
  resize: none;
  outline: none;
  max-height: 150px;
  line-height: 1.4;
}
.composer-input:focus {
  border-color: #1a73e8;
}
.btn-send {
  width: 36px;
  height: 36px;
  border: none;
  background: #1a73e8;
  color: #fff;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  flex-shrink: 0;
}
.btn-send:hover:not(:disabled) {
  background: #1557b0;
}
.btn-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #dadce0;
  border-top-color: #1a73e8;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .ws-sidebar { display: none; }
  .ws-conversations { width: 280px; min-width: 280px; }
}

@media (max-width: 767px) {
  .workspace { flex-direction: column; }
  .ws-conversations { width: 100%; min-width: 100%; flex: 1; }
  .ws-chat { flex: 1; }
  .btn-back { display: block; }
}
</style>
