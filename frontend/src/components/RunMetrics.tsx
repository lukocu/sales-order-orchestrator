import type { RunSummary } from '../api/analysis'
import { formatMs, stepCost, totalCost, totalDuration } from './format'

type Props = {
  run: RunSummary | null
  // Heading and region name; two runs in one panel need different names.
  label?: string
}

// The steps of one run with their model, tokens, cost and duration, and the run totals.
function RunMetrics({ run, label = 'Metrics' }: Props) {
  if (run === null) return <p className="muted">{label} unavailable</p>
  const totals = run.totals
  return (
    <section className="metrics" aria-label={label}>
      <h4 className="analysis__subheading">{label}</h4>
      <ul className="metrics__steps">
        {run.steps.map((step) => (
          <li key={step.id} className="metrics__step">
            <p className="metrics__name">
              {step.name} <span className="muted">· {step.kind}</span>
              {step.status === 'failed' && (
                <span className="error">
                  {' '}
                  · failed{step.error_type ? ` (${step.error_type})` : ''}
                </span>
              )}
            </p>
            <dl className="metrics__list">
              <dt>Model</dt>
              <dd>{step.model ?? '—'}</dd>
              <dt>Tokens</dt>
              <dd>
                {step.input_tokens} in / {step.output_tokens} out
              </dd>
              <dt>Cost</dt>
              <dd>{stepCost(step)}</dd>
              <dt>Duration</dt>
              <dd>{formatMs(step.duration_ms)}</dd>
            </dl>
          </li>
        ))}
        <li className="metrics__step metrics__step--total">
          <p className="metrics__name">Total</p>
          <dl className="metrics__list">
            <dt>Tokens</dt>
            <dd>
              {totals.input_tokens} in / {totals.output_tokens} out
            </dd>
            <dt>Cost</dt>
            <dd>{totalCost(run)}</dd>
            <dt>Duration</dt>
            <dd>{totalDuration(run)}</dd>
          </dl>
        </li>
      </ul>
    </section>
  )
}

export default RunMetrics
