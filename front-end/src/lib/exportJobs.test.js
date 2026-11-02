import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { removeToken, saveToken } from './auth'
import { jsonResponse, mockApi, requestsMade } from '../test/helpers'
import customToaster from '../utils/customToaster'
import { enqueueExport, followExport, GIVE_UP_AFTER_MS, POLL_INTERVAL_MS } from './exportJobs'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const job = (status, extra = {}) => ({ data: { id: 7, format: 'xlsx', status, filename: null, error: null, ...extra } })
const file = () => Promise.resolve(new Response('bytes', { status: 200 }))

describe('export jobs', () => {
  let saved
  beforeEach(() => {
    vi.mocked(customToaster).mockClear()
    saveToken('tok')
    saved = []
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      saved.push(this.download)
    })
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('enqueueExport', () => {
    it('queues the export with the chosen format and the user token, and says it is queued', async () => {
      const api = mockApi({ 'POST /exports': () => jsonResponse(job('queued'), 202) })

      const queued = await enqueueExport('xlsx')

      expect(queued).toEqual(job('queued').data)
      const [, options] = api.mock.calls[0]
      expect(JSON.parse(options.body)).toEqual({ format: 'xlsx' })
      expect(options.headers.Authorization).toBe('Bearer tok')
      expect(customToaster).toHaveBeenCalledWith('Exportação na fila', 'info', expect.stringContaining('Excel'))
    })

    it('says an export is already in progress when the server answers 409', async () => {
      mockApi({ 'POST /exports': () => jsonResponse({ detail: 'Você já tem uma exportação em andamento.' }, 409) })

      expect(await enqueueExport('csv')).toBeNull()

      expect(customToaster).toHaveBeenCalledTimes(1)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('em andamento'))
    })

    it('says it could not queue the export when the server refuses or cannot be reached', async () => {
      mockApi({ 'POST /exports': () => jsonResponse({ detail: 'boom' }, 500) })
      expect(await enqueueExport('csv')).toBeNull()

      mockApi({ 'POST /exports': () => Promise.reject(new TypeError('Failed to fetch')) })
      vi.spyOn(console, 'error').mockImplementation(() => {})
      expect(await enqueueExport('csv')).toBeNull()

      expect(customToaster).toHaveBeenCalledTimes(2)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('iniciar a exportação'))
      expect(customToaster).not.toHaveBeenCalledWith('Exportação na fila', expect.anything(), expect.anything())
    })
  })

  describe('followExport', () => {
    it('waits while the job is queued and running, then downloads the file and says it is done', async () => {
      const states = [job('queued'), job('running'), job('done', { filename: 'transacoes-2026-03-15.xlsx' })]
      const api = mockApi({
        'GET /exports/7': () => jsonResponse(states.shift()),
        'GET /exports/7/file': file,
      })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
      await finished

      expect(requestsMade(api)).toEqual(['GET /exports/7', 'GET /exports/7', 'GET /exports/7', 'GET /exports/7/file'])
      expect(saved).toEqual(['transacoes-2026-03-15.xlsx']) // named by the server
      expect(customToaster).toHaveBeenCalledWith('Exportação concluída', 'success', expect.stringContaining('transacoes-2026-03-15.xlsx'))
    })

    it('does not download anything while the job is not done', async () => {
      const api = mockApi({ 'GET /exports/7': () => jsonResponse(job('running')) })

      followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)

      expect(requestsMade(api).every((r) => r === 'GET /exports/7')).toBe(true)
      expect(saved).toEqual([])
      expect(customToaster).not.toHaveBeenCalled()
    })

    it('tells the user when the job failed and downloads nothing', async () => {
      mockApi({ 'GET /exports/7': () => jsonResponse(job('failed', { error: 'x' })) })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('gerar o arquivo'))
      expect(saved).toEqual([])
    })

    it('keeps trying through a hiccup in the connection', async () => {
      let calls = 0
      mockApi({
        'GET /exports/7': () => (++calls === 1 ? Promise.reject(new TypeError('Failed to fetch')) : jsonResponse(job('done', { filename: 'a.csv' }))),
        'GET /exports/7/file': file,
      })
      vi.spyOn(console, 'error').mockImplementation(() => {})

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2)
      await finished

      expect(saved).toEqual(['a.csv'])
    })

    it('stops with a message when the job no longer exists', async () => {
      const api = mockApi({ 'GET /exports/7': () => jsonResponse({ detail: 'Export not found' }, 404) })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(requestsMade(api)).toEqual(['GET /exports/7'])
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('Não encontramos'))
    })

    it.each([401, 403])('stops and says the session ended when the server answers %i', async (code) => {
      const api = mockApi({ 'GET /exports/7': () => jsonResponse({ detail: 'Token expired' }, code) })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(requestsMade(api)).toEqual(['GET /exports/7']) // not retried for two minutes
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('sessão expirou'))
    })

    it('stops quietly, without downloading, when the user logs out while waiting', async () => {
      const api = mockApi({ 'GET /exports/7': () => jsonResponse(job('running')) })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS) // first poll
      removeToken()
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
      await finished

      expect(requestsMade(api)).toEqual(['GET /exports/7'])
      expect(saved).toEqual([])
      expect(customToaster).not.toHaveBeenCalled()
    })

    it('tells the user when the file cannot be downloaded', async () => {
      mockApi({
        'GET /exports/7': () => jsonResponse(job('done', { filename: 'a.csv' })),
        'GET /exports/7/file': () => jsonResponse({ detail: 'boom' }, 500),
      })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
      await finished

      expect(saved).toEqual([])
      expect(customToaster).toHaveBeenCalledTimes(1)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('não foi possível baixá-lo'))
      expect(customToaster).not.toHaveBeenCalledWith('Exportação concluída', expect.anything(), expect.anything())
    })

    it('gives up with a message when the job never finishes', async () => {
      const api = mockApi({ 'GET /exports/7': () => jsonResponse(job('running')) })

      const finished = followExport({ id: 7 })
      await vi.advanceTimersByTimeAsync(GIVE_UP_AFTER_MS + POLL_INTERVAL_MS * 2)
      await finished

      expect(customToaster).toHaveBeenCalledTimes(1)
      expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.stringContaining('não terminou'))
      const polled = requestsMade(api).length
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 5)
      expect(requestsMade(api).length).toBe(polled) // it stopped asking
    })
  })
})
