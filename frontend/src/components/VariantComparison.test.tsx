import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RecommendationOption, RecommendationView } from '../api/analysis'
import {
  ACME_RECOMMENDATION,
  ACME_STOCK_OPTION,
  ACME_SUBSTITUTE_OPTION,
} from '../test/recommendationFixtures'
import VariantComparison from './VariantComparison'

function renderComparison(
  recommendation: RecommendationView = ACME_RECOMMENDATION,
  expectedDeadline: string | null = '2026-11-06',
) {
  render(<VariantComparison recommendation={recommendation} expectedDeadline={expectedDeadline} />)
}

function deadlineCells(): string[] {
  return within(screen.getByRole('row', { name: /^Deadline/ }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

function withFulfilled(option: RecommendationOption, fulfilledOn: string): RecommendationOption {
  return { ...option, fulfilled_on: fulfilledOn }
}

describe('VariantComparison', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })


  it('is a table named by its caption with column and row headers', () => {
    renderComparison()

    const table = screen.getByRole('table', { name: 'Variant comparison' })
    expect(within(table).getAllByRole('columnheader')).toHaveLength(4)
    expect(
      within(table)
        .getAllByRole('rowheader')
        .map((header) => header.textContent),
    ).toEqual(['Coverage', 'Deadline', 'Value', 'Margin', 'Risks', 'Confidence'])
  })

  it('puts the recommended variant first and labels it', () => {
    renderComparison()

    const headers = screen.getAllByRole('columnheader').slice(1)
    expect(headers[0]).toHaveTextContent('Stock + substitute ABC-110')
    expect(within(headers[0]).getByText('Recommended')).toBeInTheDocument()
    expect(screen.getAllByText('Recommended')).toHaveLength(1)
  })

  it('keeps build order and recommends nothing when the recommendation failed', () => {
    renderComparison({ ...ACME_RECOMMENDATION, status: 'failed', choice: null })

    const headers = screen.getAllByRole('columnheader').slice(1)
    expect(headers.map((header) => header.textContent)).toEqual([
      'Stock only (partial delivery)',
      'Stock + substitute ABC-110',
      'Stock + supplier Sensortech Polska',
    ])
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument()
  })

  it('states the deadline relation as late, early, on the day or none', () => {
    renderComparison({
      ...ACME_RECOMMENDATION,
      choice: null,
      status: 'failed',
      options: [
        withFulfilled(ACME_STOCK_OPTION, '2026-11-07'),
        withFulfilled(ACME_SUBSTITUTE_OPTION, '2026-11-06'),
        withFulfilled({ ...ACME_STOCK_OPTION, id: 'x' }, '2026-11-09'),
        withFulfilled({ ...ACME_STOCK_OPTION, id: 'y' }, '2026-11-05'),
      ],
    })

    expect(deadlineCells()).toEqual([
      '2026-11-07, 1 day after the deadline',
      '2026-11-06, on the deadline',
      '2026-11-09, 3 days after the deadline',
      '2026-11-05, 1 day before the deadline',
    ])
  })

  it('says there is no deadline whatever the stored verdict is', () => {
    renderComparison(ACME_RECOMMENDATION, null)

    expect(deadlineCells().every((cell) => cell.endsWith(', no deadline'))).toBe(true)
  })

  it('lists only the risk signals in the risks row, or none', () => {
    renderComparison()

    const cells = within(screen.getByRole('row', { name: /^Risks/ })).getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('none')
    expect(cells[1]).toHaveTextContent('Covers 50 of 80 pcs')
    expect(cells[1]).not.toHaveTextContent('Delivery meets the customer’s deadline')
  })

  it('has one details per variant, the recommended one open with cited marks', () => {
    renderComparison()

    const details = Array.from(document.querySelectorAll('details'))
    expect(details).toHaveLength(3)
    expect(details.map((item) => item.hasAttribute('open'))).toEqual([true, false, false])
    expect(details[0].querySelector('summary')).toHaveTextContent('Stock + substitute ABC-110')
    expect(details[0]).toHaveTextContent('30 × ABC-110')
    expect(details[0]).toHaveTextContent('Cost: 6900.00 PLN')
    expect(details[0].textContent).toContain('· cited')
    expect(details[1].textContent).not.toContain('· cited')
    expect(details[2]).toHaveTextContent('Delivery on 9 Nov 2026 is after the deadline of 6 Nov 2026')
  })

  it('tells two substitutes apart by name', () => {
    const other: RecommendationOption = {
      ...ACME_SUBSTITUTE_OPTION,
      id: 'stock+ABC-120',
      lines: [
        ACME_SUBSTITUTE_OPTION.lines[0],
        { ...ACME_SUBSTITUTE_OPTION.lines[1], product_code: 'ABC-120' },
      ],
    }
    renderComparison({
      ...ACME_RECOMMENDATION,
      options: [ACME_SUBSTITUTE_OPTION, other],
    })

    const names = screen
      .getAllByRole('columnheader')
      .slice(1)
      .map((header) => header.textContent)
    expect(names[0]).toContain('substitute ABC-110')
    expect(names[1]).toBe('Stock + substitute ABC-120')
  })

  describe('scroll region', () => {
    it('is a focusable region named by the caption, with no hint when everything fits', () => {
      renderComparison()

      const region = screen.getByRole('region', { name: 'Variant comparison' })
      expect(region).toHaveAttribute('tabindex', '0')
      expect(region).toContainElement(screen.getByRole('table'))
      expect(region).not.toHaveAttribute('aria-describedby')
      expect(screen.queryByText(/scroll sideways/)).not.toBeInTheDocument()
    })

    it('shows the hint and references it when the variants overflow', async () => {
      vi.stubGlobal(
        'ResizeObserver',
        class {
          observe() {}
          disconnect() {}
          unobserve() {}
        },
      )
      vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(900)
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(375)

      renderComparison()

      const hint = await screen.findByText('Variants: 3 — scroll sideways to see them all')
      const region = screen.getByRole('region', { name: 'Variant comparison' })
      expect(region).toHaveAccessibleDescription(hint.textContent ?? '')
      expect(region.getAttribute('aria-describedby')).toBe(hint.id)
    })
  })
})
