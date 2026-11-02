import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, networkDown, renderApp } from '../test/helpers'
import Chatbot from './Chatbot'

const input = () => screen.getByPlaceholderText('Digite sua mensagem...')
const sendButton = () => screen.getByRole('button', { name: 'Send message' })

const sentBody = (api) => JSON.parse(api.mock.calls.find(([url]) => url.endsWith('/webhook/'))[1].body)
const sentText = (api) => sentBody(api).entry[0].changes[0].value.messages[0]

describe('chatbot', () => {
  it('greets the user', () => {
    renderApp(<Chatbot />)

    expect(screen.getByText('Olá! Como posso te ajudar hoje?')).toBeInTheDocument()
  })

  it('does not allow sending an empty or blank message', async () => {
    const api = mockApi({})
    renderApp(<Chatbot />)

    expect(sendButton()).toBeDisabled()
    await userEvent.type(input(), '   ')
    expect(sendButton()).toBeDisabled()
    await userEvent.type(input(), '{Enter}')

    expect(api).not.toHaveBeenCalled()
  })

  it('sends the message to the webhook as a WhatsApp message from the user, and shows the reply', async () => {
    saveToken('tok')
    const api = mockApi({
      'GET /user/me': { data: { whatsapp_phone: '5511999990000' } },
      'POST /webhook/': { status: 'success', reply: 'Registrado! R$ 10,00' },
    })
    renderApp(<Chatbot />)
    await waitFor(() => expect(api).toHaveBeenCalledTimes(1)) // the profile was loaded

    await userEvent.type(input(), '  gastei 10 de almoço ')
    await userEvent.click(sendButton())

    expect(await screen.findByText('Registrado! R$ 10,00')).toBeInTheDocument()
    expect(screen.getByText('gastei 10 de almoço')).toBeInTheDocument()
    expect(sentText(api)).toEqual({ from: '5511999990000', text: { body: 'gastei 10 de almoço' } })
    expect(input()).toHaveValue('')
  })

  it('uses a placeholder number when the user has no WhatsApp number', async () => {
    const api = mockApi({ 'POST /webhook/': { reply: 'ok' } })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi')
    await userEvent.click(sendButton())
    await screen.findByText('ok')

    expect(sentText(api).from).toBe('00000000000')
  })

  it('sends with Enter', async () => {
    const api = mockApi({ 'POST /webhook/': { reply: 'ok' } })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi{Enter}')

    expect(await screen.findByText('ok')).toBeInTheDocument()
    expect(api).toHaveBeenCalledTimes(1)
  })

  it('shows "Digitando..." while waiting and blocks a second send', async () => {
    let answer
    mockApi({ 'POST /webhook/': () => new Promise((resolve) => { answer = () => resolve(new Response(JSON.stringify({ reply: 'pronto' }))) }) })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi')
    await userEvent.click(sendButton())

    expect(screen.getByText('Digitando...')).toBeInTheDocument()
    expect(sendButton()).toBeDisabled()
    answer()
    expect(await screen.findByText('pronto')).toBeInTheDocument()
    expect(screen.queryByText('Digitando...')).not.toBeInTheDocument()
  })

  it('apologises when the server answers with an error', async () => {
    mockApi({ 'POST /webhook/': [{ status: 'error', message: 'boom' }, 500] })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi')
    await userEvent.click(sendButton())

    expect(await screen.findByText('Desculpe, ocorreu um erro ao processar sua mensagem.')).toBeInTheDocument()
  })

  it('apologises when the server answers without a reply', async () => {
    // e.g. the webhook acknowledged the message but the chatbot produced nothing
    mockApi({ 'POST /webhook/': { status: 'error', message: 'boom' } })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi')
    await userEvent.click(sendButton())

    expect(await screen.findByText('Desculpe, ocorreu um erro ao processar sua mensagem.')).toBeInTheDocument()
  })

  it('reports a connection problem when the network is down', async () => {
    networkDown()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'oi')
    await userEvent.click(sendButton())

    expect(await screen.findByText('Erro de conexão ao tentar enviar a mensagem.')).toBeInTheDocument()
    expect(sendButton()).toBeDisabled() // input is empty again, and we are no longer loading
  })

  it('keeps the conversation in order', async () => {
    mockApi({ 'POST /webhook/': () => jsonResponse({ reply: 'resposta' }) })
    renderApp(<Chatbot />)

    await userEvent.type(input(), 'primeira{Enter}')
    await screen.findByText('resposta')

    const [greeting, mine, reply] = ['Olá! Como posso te ajudar hoje?', 'primeira', 'resposta'].map((t) => screen.getByText(t))
    expect(greeting.compareDocumentPosition(mine) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(mine.compareDocumentPosition(reply) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('pressing Enter while waiting for a reply does not send a second message', async () => {
    let answer
    const api = mockApi({
      'POST /webhook/': () => new Promise((resolve) => { answer = () => resolve(new Response(JSON.stringify({ reply: 'pronto' }))) }),
    })
    renderApp(<Chatbot />)
    await userEvent.type(input(), 'primeira{Enter}')

    await userEvent.type(input(), 'segunda{Enter}')

    expect(api).toHaveBeenCalledTimes(1)
    answer()
    await screen.findByText('pronto')
  })
})
