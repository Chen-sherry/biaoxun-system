import { defineStore } from 'pinia'
import request from '@/utils/request'
import { TOKEN_KEY } from '@/utils/request'

interface UserInfo {
  id: number
  username: string
  nickname?: string
  avatar?: string
  company?: string
  roles?: string[]
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    info: null as UserInfo | null,
    _fetching: null as Promise<UserInfo> | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token && !!s.info,
  },
  actions: {
    async login(username: string, password: string) {
      const data: { access_token: string } = await request.post('/api/v1/auth/login', {
        username,
        password,
      })
      this.token = data.access_token
      localStorage.setItem(TOKEN_KEY, data.access_token)
      this.info = null
      this._fetching = null
      await this.fetchInfo()
      return data
    },
    async fetchInfo() {
      // 防并发：如果已经在请求，直接复用同一个 Promise
      if (this.info) return this.info
      if (this._fetching) return this._fetching
      this._fetching = request.get<UserInfo>('/api/v1/auth/me').then((data) => {
        this.info = data
        return data
      }).finally(() => {
        this._fetching = null
      })
      return this._fetching
    },
    logout() {
      this.token = ''
      this.info = null
      this._fetching = null
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
