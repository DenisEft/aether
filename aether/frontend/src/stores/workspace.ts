import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Channel, Conversation, Message, Organisation } from '../shared/types/client'
import { useApi } from '../shared/composables/useApi'

export const useWorkspaceStore = defineStore('workspace', () => {
  const channels = ref<Channel[]>([])
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const organisations = ref<Organisation[]>([])
  const loading = ref(false)

  async function loadChannels() {
    try {
      const api = useApi()
      const { data } = await api.get<Channel[]>('/channels')
      channels.value = data
    } catch (e: unknown) {
      console.error('[workspace store] Failed to load channels', e)
    }
  }

  async function loadConversations() {
    loading.value = true
    try {
      const api = useApi()
      const { data } = await api.get<Conversation[]>('/conversations')
      conversations.value = data
    } finally {
      loading.value = false
    }
  }

  async function loadMessages(conversationId: string) {
    try {
      const api = useApi()
      const { data } = await api.get<Message[]>(`/conversations/${conversationId}/messages`)
      messages.value = data
    } catch (e: unknown) {
      console.error('[workspace store] Failed to load messages for conversation', conversationId, e)
      messages.value = []
    }
  }

  function selectConversation(id: string | null) {
    activeConversationId.value = id
    if (id) loadMessages(id)
  }

  async function sendMessage(conversationId: string, text: string) {
    try {
      const api = useApi()
      await api.post(`/conversations/${conversationId}/messages`, {
        role: 'user',
        content: text,
      })
      await loadMessages(conversationId)
    } catch (e: unknown) {
      console.error('[workspace store] Failed to send message to conversation', conversationId, e)
    }
  }

  return {
    channels,
    conversations,
    activeConversationId,
    messages,
    organisations,
    loading,
    loadChannels,
    loadConversations,
    loadMessages,
    selectConversation,
    sendMessage,
  }
})
