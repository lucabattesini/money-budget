import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { removeToken, saveToken } from './auth'
import { jsonResponse, mockApi, requestsMade } from '../test/helpers'
import customToaster from '../utils/customToaster'
import { followImport, GIVE_UP_AFTER_MS, POLL_INTERVAL_MS, queueImport } from './importJobs'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const job = (status, extra = {}) => ({ data: { id: 5, status, imported_count: null, skipped_count: null, error: null, ...extra } })

describe('import jobs', () => {
  beforeEach(() => {
    vi.mocked(customToaster).mockClear()
    saveToken('tok')
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('queueImport', () => {
    it('starts the import with the login and says it is queued', async () => {
      const api = mockApi({ 'POST /imports/5/start': () => jsonResponse(job('queued'), 202) })

      const queued = await queueImport(5)

      expect(queued).toEqual(job('queued').data)
      expect(api.mock.calls[0][1].headers.Authorization).toBe('Bearer tok')
      expect(customToaster).toHaveBeenCalledWith('Importação na fila', 'info', expect.any(String))
    })

    it('repeats what the server says when it refuses, for example that one is already running', async () => {
      mockApi({ 'POST /imports/5/start': () => jsonResponse({ detail: 'Já existe uma importação em andamento na sua família.' }, 409) })

      expect(await queueImport(5)).toBeNull()

      expect(customToaster).toHaveBeenCalledTimes(1)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', 'Já existe uma importação em andamento na sua família.')
    })

    it('says it could not start when the server fails or cannot be reached', async () => {
      mockApi({ 'POST /imports/5/start': () => jsonResponse({ detail: 'boom' }, 500) })
      expect(await queueImport(5)).toBeNull()

      mockApi({ 'POST /imports/5/start': () => Promise.reject(new TypeError('Failed to fetch')) })
      vi.spyOn(console, 'error').mockImplementation(() => {})
      expect(await queueImport(5)).toBeNull()

      expect(customToaster).toHaveBeenCalledTimes(2)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('iniciar a importação'))
      expect(customToaster).not.toHaveBeenCalledWith('Erro', 'error', 'boom') // details stay in the log
    })
  })

  describe('followImport', () => {
    it('waits while the job runs, then says how many rows were imported and skipped', async () => {
      const states = [job('queued'), job('running'), job('done', { imported_count: 12, skipped_count: 3 })]
      const api = mockApi({ 'GET /imports/5': () => jsonResponse(states.shift()) })

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
      await finished

      expect(requestsMade(api)).toEqual(['GET /imports/5', 'GET /imports/5', 'GET /imports/5'])
      expect(customToaster).toHaveBeenCalledTimes(1)
      expect(customToaster).toHaveBeenCalledWith(
        'Importação concluída',
        'success',
        '12 transações importadas e 3 ignoradas porque já existiam.',
      )
    })

    it('does not mention skipped rows when there were none, and uses the singular', async () => {
      mockApi({ 'GET /imports/5': () => jsonResponse(job('done', { imported_count: 1, skipped_count: 0 })) })

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Importação concluída', 'success', '1 transação importada.')
    })

    it('says so when everything was skipped', async () => {
      mockApi({ 'GET /imports/5': () => jsonResponse(job('done', { imported_count: 0, skipped_count: 1 })) })

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Importação concluída', 'success', '0 transações importadas e 1 ignorada porque já existia.')
    })

    it('does not announce anything while the job is not done', async () => {
      mockApi({ 'GET /imports/5': () => jsonResponse(job('running')) })

      followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)

      expect(customToaster).not.toHaveBeenCalled()
    })

    it('tells the user a failed import saved nothing', async () => {
      mockApi({ 'GET /imports/5': () => jsonResponse(job('failed', { error: 'Não foi possível importar o arquivo.' })) })

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', 'Não foi possível importar o arquivo. Nada foi importado.')
    })

    it('keeps trying through a hiccup in the connection', async () => {
      let calls = 0
      mockApi({
        'GET /imports/5': () => (++calls === 1 ? Promise.reject(new TypeError('Failed to fetch')) : jsonResponse(job('done', { imported_count: 2, skipped_count: 0 }))),
      })
      vi.spyOn(console, 'error').mockImplementation(() => {})

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Importação concluída', 'success', '2 transações importadas.')
    })

    it('stops with a message when the job no longer exists or the login expired', async () => {
      const api = mockApi({ 'GET /imports/5': () => jsonResponse({ detail: 'Import not found' }, 404) })
      let finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished
      expect(requestsMade(api)).toEqual(['GET /imports/5'])
      expect(customToaster).toHaveBeenLastCalledWith('Erro', 'error', expect.stringContaining('Não encontramos'))

      mockApi({ 'GET /imports/5': () => jsonResponse({ detail: 'x' }, 403) })
      finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished
      expect(customToaster).toHaveBeenLastCalledWith('Erro', 'error', expect.stringContaining('sessão expirou'))
    })

    it('stops quietly when the user logged out', async () => {
      const api = mockApi({})
      removeToken()

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(requestsMade(api)).toEqual([])
      expect(customToaster).not.toHaveBeenCalled()
    })

    it('gives up after a while with a message', async () => {
      mockApi({ 'GET /imports/5': () => jsonResponse(job('running')) })

      const finished = followImport({ id: 5 })
      await vi.advanceTimersByTimeAsync(GIVE_UP_AFTER_MS + POLL_INTERVAL_MS)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('não terminou'))
    })
  })
})
