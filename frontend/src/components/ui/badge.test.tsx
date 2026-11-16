import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Badge } from './badge'

describe('Badge status variants', () => {
  it('fills the warning badge with the warning tokens', () => {
    render(<Badge variant="warning">Awaiting supervisor</Badge>)
    const badge = screen.getByText('Awaiting supervisor')
    expect(badge).toHaveAttribute('data-variant', 'warning')
    expect(badge).toHaveClass('bg-warning', 'text-warning-foreground')
  })

  it('outlines the success badge in the success token', () => {
    render(<Badge variant="success-outline">Standard</Badge>)
    const badge = screen.getByText('Standard')
    expect(badge).toHaveClass('border-success', 'text-success')
    expect(badge).not.toHaveClass('bg-success')
  })
})
