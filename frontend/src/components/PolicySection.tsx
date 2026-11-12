import { useState } from 'react'
import type {
  PolicyOutcome,
  PolicyView,
  RecommendationView,
  RuleCode,
  RuleResult,
  RuleVerdict,
} from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { formatDate, formatPercent, formatPln } from './format'
import RunMetrics from './RunMetrics'

type Props = {
  inquiryId: number
  // null while there is no verdict for the current recommendation.
  policy: PolicyView | null
  // The recommendation the verdict is evaluated on; tells why there is none.
  recommendation: RecommendationView | null
  // True while the panel analyzes, saves or re-runs the checks, the orchestrator, the
  // recommendation or the policy.
  disabled: boolean
  // True while the panel re-runs the policy.
  running: boolean
  // Re-runs the policy and shows the result; rejects when the re-run failed.
  onRerun: () => Promise<void>
  // Called whenever the API answers 401 (session gone).
  onUnauthorized: () => void
}

// Every verdict is shown as text; the tone only adds the colour.
type Tone = 'ok' | 'warn' | 'error'

const OUTCOME: Record<PolicyOutcome, [string, Tone]> = {
  no_approval_needed: ['No approval needed', 'ok'],
  requires_supervisor: ['Requires supervisor approval', 'warn'],
}

const RULE: Record<RuleCode, string> = {
  margin: 'Margin',
  discount: 'Discount',
  order_value: 'Order value',
  credit: 'Credit',
}

// How the actual value must compare with the threshold to pass.
const COMPARATOR: Record<RuleCode, string> = {
  margin: '≥',
  discount: '≤',
  order_value: '≤',
  credit: '≤',
}

const VERDICT: Record<RuleVerdict, [string, Tone]> = {
  pass: ['Pass', 'ok'],
  fail: ['Fail', 'error'],
  not_evaluated: ['Not evaluated', 'warn'],
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

// Why there cannot be a (current) verdict; null when the recommendation allows one.
function blockedReason(recommendation: RecommendationView | null): string | null {
  if (recommendation === null) return 'No policy verdict: there is no recommendation yet.'
  if (recommendation.status === 'failed') return 'No policy verdict: the recommendation failed.'
  if (recommendation.stale) {
    return 'No policy verdict: the recommendation is out of date; re-run the recommendation first.'
  }
  return null
}

function amount(rule: RuleResult, value: string | null): string {
  if (value === null) return '—'
  return rule.unit === 'percent' ? formatPercent(value) : formatPln(value)
}

function thresholdText(rule: RuleResult): string {
  if (rule.threshold === null) return '—'
  const text = `${COMPARATOR[rule.code]} ${amount(rule, rule.threshold)}`
  return rule.code === 'credit' ? `${text} (credit limit)` : text
}

// The policy verdict on the recommended option: each rule against its threshold, the overall
// outcome and the run's cost.
function PolicySection({
  inquiryId,
  policy,
  recommendation,
  disabled,
  running,
  onRerun,
  onUnauthorized,
}: Props) {
  const [error, setError] = useState<string | null>(null)
  const headingId = `policy-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure))
    }
  }

  const blocked = blockedReason(recommendation)
  const outdated = policy === null || policy.stale
  const offerRerun = blocked === null && outdated

  return (
    <section className="orchestration policy" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        Policy
      </h4>

      {blocked !== null && outdated && <p className="checks__line">{blocked}</p>}
      {blocked === null && policy === null && (
        <p className="checks__line">Policy not evaluated yet</p>
      )}
      {policy?.stale && (
        <p className="checks__line">
          The recommendation changed after this verdict was evaluated; the result may be out of
          date.
        </p>
      )}
      {offerRerun && (
        <div className="analysis__actions">
          <button type="button" onClick={rerun} disabled={disabled}>
            {running ? 'Running policy…' : 'Re-run policy'}
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">Re-running the policy failed: {error}</p>
          <button type="button" onClick={rerun} disabled={disabled}>
            Retry
          </button>
        </div>
      )}

      {policy !== null && <PolicyResult policy={policy} />}
    </section>
  )
}

function PolicyResult({ policy }: { policy: PolicyView }) {
  const [outcome, tone] = OUTCOME[policy.outcome]
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="check__head">
          <span className="checks__outcome">{outcome}</span>
          {policy.thresholds_are_examples && (
            <span className="policy__example">Example thresholds</span>
          )}
        </p>
      </div>
      <p className="analysis__meta">
        Evaluated {formatDate(policy.evaluated_at)} · option {policy.option_id}
      </p>

      <div className="policy__table-wrap">
        <table className="policy__table">
          <caption className="orchestration__stage-title">Policy rules</caption>
          <thead>
            <tr>
              <th scope="col">Rule</th>
              <th scope="col">Actual</th>
              <th scope="col">Threshold</th>
              <th scope="col">Verdict</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {policy.rules.map((rule) => {
              const [verdict, verdictTone] = VERDICT[rule.verdict]
              return (
                <tr key={rule.code}>
                  <th scope="row">{RULE[rule.code]}</th>
                  <td>{amount(rule, rule.actual)}</td>
                  <td>{thresholdText(rule)}</td>
                  <td>
                    <span className={`check__status check__status--${verdictTone}`}>
                      {verdict}
                    </span>
                  </td>
                  <td>{rule.reason}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <RunMetrics run={policy.run} label="Policy metrics" />
    </>
  )
}

export default PolicySection
