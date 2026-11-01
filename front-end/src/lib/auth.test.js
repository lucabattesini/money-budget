import { describe, expect, it } from 'vitest'
import { authHeaders, getToken, isAuthenticated, removeToken, saveToken } from './auth'

describe('auth token storage', () => {
  it('starts logged out', () => {
    expect(getToken()).toBeNull()
    expect(isAuthenticated()).toBe(false)
  })

  it('keeps the token after saving it', () => {
    saveToken('abc')

    expect(getToken()).toBe('abc')
    expect(isAuthenticated()).toBe(true)
  })

  it('stores the token in localStorage under auth_token', () => {
    saveToken('abc')

    expect(localStorage.getItem('auth_token')).toBe('abc')
  })

  it('logs out when the token is removed', () => {
    saveToken('abc')

    removeToken()

    expect(getToken()).toBeNull()
    expect(isAuthenticated()).toBe(false)
  })

  it('replaces an older token', () => {
    saveToken('old')
    saveToken('new')

    expect(getToken()).toBe('new')
  })
})

describe('authHeaders', () => {
  it('is empty without a token', () => {
    expect(authHeaders()).toEqual({})
  })

  it('sends the token as a Bearer header', () => {
    saveToken('abc')

    expect(authHeaders()).toEqual({ Authorization: 'Bearer abc' })
  })
})
