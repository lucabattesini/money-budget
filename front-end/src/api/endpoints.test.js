import { describe, expect, it, vi } from 'vitest'
import {
  deleteTransaction,
  getAllCategories,
  getMe,
  getSummedTransactionsByCategory,
  getTransactions,
  insertNewTransaction,
  loginWithGoogle,
  updatePhone,
} from './endpoints'
import { saveToken, getToken } from '../lib/auth'
import { mockApi, networkDown } from '../test/helpers'

const lastCall = (mock) => {
  const [url, options] = mock.mock.calls.at(-1)
  return { url, options, body: options.body ? JSON.parse(options.body) : undefined }
}

describe('loginWithGoogle', () => {
  it('posts the Google token and the phone to /auth/google', async () => {
    const api = mockApi({ 'POST /auth/google': { data: { token: 't' } } })

    const result = await loginWithGoogle('google-token', '5511999990000')

    expect(result).toEqual({ data: { token: 't' } })
    const { url, options, body } = lastCall(api)
    expect(url).toBe('http://api.test/auth/google')
    expect(options.method.toUpperCase()).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(body).toEqual({ id_token: 'google-token', whatsapp_phone: '5511999990000' })
  })

  it('returns nothing, and logs, when the server refuses the login', async () => {
    mockApi({ 'POST /auth/google': [{ detail: 'Invalid Google token' }, 401] })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})

    const result = await loginWithGoogle('bad', null)

    expect(result).toBeUndefined()
    expect(log).toHaveBeenCalled()
  })

  it('returns nothing, and logs, when the network fails', async () => {
    networkDown()
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(await loginWithGoogle('t', null)).toBeUndefined()
    expect(log).toHaveBeenCalled()
  })
})

describe('authenticated requests', () => {
  it('getMe sends the Bearer token to /user/me', async () => {
    const api = mockApi({ 'GET /user/me': { data: { id: 1 } } })

    expect(await getMe('tok')).toEqual({ data: { id: 1 } })
    expect(lastCall(api).url).toBe('http://api.test/user/me')
    expect(lastCall(api).options.headers.Authorization).toBe('Bearer tok')
  })

  it('updatePhone patches /user/me/phone with the number', async () => {
    const api = mockApi({ 'PATCH /user/me/phone': { data: { whatsapp_phone: '5511' } } })

    await updatePhone('5511', 'tok')

    const { options, body } = lastCall(api)
    expect(options.method).toBe('PATCH')
    expect(options.headers.Authorization).toBe('Bearer tok')
    expect(body).toEqual({ whatsapp_phone: '5511' })
  })

  it('updatePhone returns nothing when the server refuses', async () => {
    mockApi({ 'PATCH /user/me/phone': [{ detail: 'no' }, 404] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(await updatePhone('5511', 'tok')).toBeUndefined()
  })

  it('getAllCategories asks /categories', async () => {
    const api = mockApi({ 'GET /categories': { data: [{ id: 1, name: 'Alimentação' }] } })

    expect(await getAllCategories('tok')).toEqual({ data: [{ id: 1, name: 'Alimentação' }] })
    expect(lastCall(api).options.headers.Authorization).toBe('Bearer tok')
  })

  it.each([
    ['getTransactions', getTransactions, '/transactions'],
    ['getSummedTransactionsByCategory', getSummedTransactionsByCategory, '/transactions/summed-by-category'],
  ])('%s posts the date filter as JSON', async (_name, fn, path) => {
    const api = mockApi({ [`POST ${path}`]: { data: [] } })
    const filter = { organized_by: 'month', date: '2026-03-01T00:00:00' }

    await fn(filter, 'tok')

    const { options, body } = lastCall(api)
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(options.headers.Authorization).toBe('Bearer tok')
    expect(body).toEqual(filter)
  })

  it('deleteTransaction sends DELETE to /transactions/<id>', async () => {
    const api = mockApi({ 'DELETE /transactions/7': [{ data: {} }, 202] })

    await deleteTransaction(7, 'tok')

    expect(lastCall(api).url).toBe('http://api.test/transactions/7')
    expect(lastCall(api).options.method).toBe('delete')
    expect(lastCall(api).options.headers.Authorization).toBe('Bearer tok')
  })
})

describe('insertNewTransaction', () => {
  const payload = { label: 'Almoço', value: 2500, category_id: 3 }

  it('posts the payload to /transactions/create and reports the status', async () => {
    const api = mockApi({ 'POST /transactions/create': [{ data: {} }, 201] })

    const result = await insertNewTransaction(payload, 'tok')

    expect(result.status).toBe(201)
    expect(lastCall(api).body).toEqual(payload)
    expect(lastCall(api).options.headers.Authorization).toBe('Bearer tok')
  })

  it('returns the parsed response body, not a pending promise', async () => {
    mockApi({ 'POST /transactions/create': [{ data: { id: 1 } }, 201] })

    const result = await insertNewTransaction(payload, 'tok')

    expect(result.body).toEqual({ data: { id: 1 } })
  })

  it('tells the caller when the request failed instead of returning nothing', async () => {
    networkDown()
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const result = await insertNewTransaction(payload, 'tok')

    expect(result).toBeDefined() // some value the caller can inspect, not undefined
  })
})

describe('error responses from the read calls', () => {
  it('returns nothing, and logs, when the server answers with a page that is not JSON', async () => {
    mockApi({ 'GET /user/me': () => Promise.resolve(new Response('<h1>502 Bad Gateway</h1>', { status: 502 })) })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(await getMe('tok')).toBeUndefined()
    expect(log).toHaveBeenCalled()
  })

  it('does not hand an expired-token error to the caller as if it were data', async () => {
    mockApi({ 'POST /transactions': [{ detail: 'Token expired' }, 401] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const result = await getTransactions({ organized_by: null, date: null }, 'old')

    expect(result).toBeUndefined() // or a rejection / an explicit error the page can handle
  })
})

describe('an expired login', () => {
  it.each([
    ['getTransactions', () => getTransactions({ organized_by: null, date: null }, 'old'), 'POST /transactions'],
    ['getAllCategories', () => getAllCategories('old'), 'GET /categories'],
    ['getMe', () => getMe('old'), 'GET /user/me'],
    ['insertNewTransaction', () => insertNewTransaction({ label: 'x', value: 1, category_id: 1 }, 'old'), 'POST /transactions/create'],
  ])('%s forgets the token and sends the user to the login page', async (_name, call, route) => {
    saveToken('old')
    window.location.hash = '#/transactions'
    mockApi({ [route]: [{ detail: 'Token expired' }, 401] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    await call()

    expect(getToken()).toBeNull()
    expect(window.location.hash).toBe('#/login-google')
  })

  it('does not log the user out because of another kind of error', async () => {
    saveToken('good')
    mockApi({ 'GET /categories': [{ detail: 'boom' }, 500] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(await getAllCategories('good')).toBeUndefined()

    expect(getToken()).toBe('good')
  })
})
