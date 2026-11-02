import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { exportFileName, saveBlob } from './download'

describe('exportFileName', () => {
  it('names the file with the local day and the extension', () => {
    expect(exportFileName('xlsx', new Date(2026, 2, 5, 23, 59))).toBe('transacoes-2026-03-05.xlsx')
    expect(exportFileName('csv', new Date(2026, 11, 31))).toBe('transacoes-2026-12-31.csv')
  })
})

describe('saveBlob', () => {
  let clicked
  beforeEach(() => {
    clicked = []
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      clicked.push({ href: this.href, download: this.download })
    })
  })
  afterEach(() => vi.restoreAllMocks())

  it('downloads the blob under the given name and cleans up after itself', () => {
    const blob = new Blob(['x'])

    saveBlob(blob, 'a.csv')

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(clicked).toEqual([{ href: 'blob:fake', download: 'a.csv' }])
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake')
    expect(document.querySelector('a[download]')).toBeNull() // the temporary link is gone
  })
})
