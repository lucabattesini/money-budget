import { describe, expect, it, vi } from 'vitest'
import {
  cancelInvite,
  createCategory,
  deleteCategory,
  getCategoryGroups,
  updateCategory,
  createInvite,
  deleteTransaction,
  getFamily,
  getInvites,
  joinFamily,
  returnToPreviousFamily,
  getAllCategories,
  getMe,
  getSummedTransactionsByCategory,
  getTransactions,
  insertNewTransaction,
  updateTransaction,
  loginWithGoogle,
  updatePhone,
  updateFamilySettings,
  getBudgets,
  setBudget,
  copyBudgets,
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

    expect(result).toBeUndefined()
  })
})

describe('an expired login', () => {
  it.each([
    ['getTransactions', () => getTransactions({ organized_by: null, date: null }, 'old'), 'POST /transactions'],
    ['getAllCategories', () => getAllCategories('old'), 'GET /categories'],
    ['getMe', () => getMe('old'), 'GET /user/me'],
    ['insertNewTransaction', () => insertNewTransaction({ label: 'x', value: 1, category_id: 1 }, 'old'), 'POST /transactions/create'],
    ['updateTransaction', () => updateTransaction(1, { label: 'x', value: 1, category_id: 1 }, 'old'), 'PUT /transactions/1'],
    ['deleteTransaction', () => deleteTransaction(1, 'old'), 'DELETE /transactions/1'],
    ['updatePhone', () => updatePhone('5511999999999', 'old'), 'PATCH /user/me/phone'],
    ['getFamily', () => getFamily('old'), 'GET /families/me'],
    ['joinFamily', () => joinFamily('CODE', true, 'old'), 'POST /families/join'],
    ['returnToPreviousFamily', () => returnToPreviousFamily('old'), 'POST /families/rollback'],
    ['getCategoryGroups', () => getCategoryGroups('old'), 'GET /categories/groups'],
    ['createCategory', () => createCategory({ name: 'x' }, 'old'), 'POST /categories'],
    ['updateCategory', () => updateCategory(1, { name: 'x' }, 'old'), 'PATCH /categories/1'],
    ['deleteCategory', () => deleteCategory(1, 'old'), 'DELETE /categories/1'],
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


describe('family calls', () => {
  it('send the login token and the right route and body', async () => {
    const api = mockApi({
      'GET /families/me': { data: { id: 1 } },
      'GET /families/invites': { data: [] },
      'POST /families/invites': [{ data: { code: 'A' } }, 201],
      'DELETE /families/invites/3': { data: {} },
      'POST /families/join': { data: {} },
    })

    await getFamily('tok')
    await getInvites('tok')
    await createInvite('tok')
    await cancelInvite(3, 'tok')
    await joinFamily('AAAA-BBBB', false, 'tok')

    expect(api.mock.calls.map(([, o]) => o.headers.Authorization)).toEqual(Array(5).fill('Bearer tok'))
    expect(JSON.parse(api.mock.calls[4][1].body)).toEqual({ code: 'AAAA-BBBB', bring_data: false })
  })

  it('hand back the data on success and the server message on an error', async () => {
    mockApi({
      'GET /families/me': { data: { id: 1, role: 'owner' } },
      'POST /families/join': [{ detail: 'Código inválido, expirado ou já usado.' }, 404],
    })

    expect(await getFamily('tok')).toEqual({ ok: true, data: { id: 1, role: 'owner' } })
    expect(await joinFamily('X', true, 'tok')).toEqual({
      ok: false,
      status: 404,
      detail: 'Código inválido, expirado ou já usado.',
    })
  })

  it('say the server could not be reached, without throwing', async () => {
    networkDown()
    vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(await getFamily('tok')).toEqual({ ok: false })
  })
})


describe('category management calls', () => {
  it('send the token, the right route and the body', async () => {
    const api = mockApi({
      'POST /categories': [{ data: { id: 1 } }, 201],
      'PATCH /categories/1': { data: { id: 1 } },
      'DELETE /categories/1': { data: {} },
    })

    await createCategory({ name: 'Jogos', group_id: 2 }, 'tok')
    await updateCategory(1, { name: 'Novo' }, 'tok')
    await deleteCategory(1, 'tok')

    expect(api.mock.calls.map(([, o]) => o.headers.Authorization)).toEqual(Array(3).fill('Bearer tok'))
    expect(JSON.parse(api.mock.calls[0][1].body)).toEqual({ name: 'Jogos', group_id: 2 })
    expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({ name: 'Novo' })
  })

  it('hand back the status and the server message when it refuses', async () => {
    mockApi({ 'DELETE /categories/1': [{ detail: 'Esta categoria é usada por 2 transações.' }, 409] })

    expect(await deleteCategory(1, 'tok')).toEqual({
      ok: false,
      status: 409,
      detail: 'Esta categoria é usada por 2 transações.',
    })
  })
})

describe('the HTTP method of every call', () => {
  // A browser sends "patch" exactly as written (only GET, POST, PUT and DELETE are fixed for you), and the server's CORS
  // check refuses it, so a lower case method makes the call fail before it reaches the API. mockApi upper-cases the
  // method itself, which hides the problem in the other tests: look at what fetch really received.
  it.each([
    ['PATCH', 'updateFamilySettings', () => updateFamilySettings({ language: 'en' }, 'tok')],
    ['PATCH', 'updateCategory', () => updateCategory(1, { name: 'x' }, 'tok')],
    ['PATCH', 'updatePhone', () => updatePhone('+5511999999999', 'tok')],
    ['DELETE', 'deleteCategory', () => deleteCategory(1, 'tok')],
    ['POST', 'createCategory', () => createCategory({ name: 'x' }, 'tok')],
    ['GET', 'getFamily', () => getFamily('tok')],
    ['GET', 'getBudgets', () => getBudgets('2026-11', 'tok')],
    ['PUT', 'setBudget', () => setBudget(1, '2026-11', 100, 'tok')],
    ['POST', 'copyBudgets', () => copyBudgets('2026-10', '2026-11', 'tok')],
  ])('is sent as %s by %s', async (method, _name, call) => {
    const api = mockApi({ [`${method} /categories`]: {}, [`${method} /categories/1`]: {}, [`${method} /families/me`]: {}, [`${method} /families/me/settings`]: {}, [`${method} /user/me/phone`]: {}, [`${method} /budgets?month=2026-11`]: {}, [`${method} /budgets`]: {}, [`${method} /budgets/copy`]: {} })

    await call()

    expect(api.mock.calls.at(-1)[1].method).toBe(method)
  })
})
