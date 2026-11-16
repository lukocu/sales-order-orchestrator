import { useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { PolicyView, RecommendationView } from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate } from './format'
import { OUTCOME_LABEL, RULE_LABEL, ruleAmount, thresholdText, VERDICT_LABEL } from './policyLabels'

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

// Why there cannot be a (current) verdict; null when the recommendation allows one.
function blockedReason(recommendation: RecommendationView | null, t: TFunction): string | null {
  if (recommendation === null) return t('policy.blocked.noRecommendation')
  if (recommendation.status === 'failed') return t('policy.blocked.recommendationFailed')
  if (recommendation.stale) return t('policy.blocked.recommendationStale')
  return null
}

// The policy verdict on the recommended option: each rule against its threshold and the overall
// outcome; the run's cost is in the run inspector.
function PolicySection({
  inquiryId,
  policy,
  recommendation,
  disabled,
  running,
  onRerun,
  onUnauthorized,
}: Props) {
  const { t } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const headingId = `policy-${inquiryId}-heading`

  async function rerun() {
    setError(null)
    try {
      await onRerun()
    } catch (failure) {
      if (failure instanceof UnauthorizedError) onUnauthorized()
      else setError(errorMessage(failure, t))
    }
  }

  const blocked = blockedReason(recommendation, t)
  const outdated = policy === null || policy.stale
  const offerRerun = blocked === null && outdated

  return (
    <section className="orchestration policy" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        {t('policy.heading')}
      </h4>

      {blocked !== null && outdated && <p className="checks__line">{blocked}</p>}
      {blocked === null && policy === null && (
        <p className="checks__line">{t('policy.notEvaluated')}</p>
      )}
      {policy?.stale && <p className="checks__line">{t('policy.stale')}</p>}
      {offerRerun && (
        <div className="analysis__actions">
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {running ? t('policy.running') : t('policy.rerun')}
          </Button>
        </div>
      )}
      {error && (
        <div role="alert" className="analysis__problem">
          <p className="error">{t('policy.rerunFailed', { message: error })}</p>
          <Button type="button" variant="outline" onClick={rerun} disabled={disabled}>
            {t('common.retry')}
          </Button>
        </div>
      )}

      {policy !== null && <PolicyResult policy={policy} />}
    </section>
  )
}

function PolicyResult({ policy }: { policy: PolicyView }) {
  const { t } = useTranslation()
  const { key: outcomeKey, tone } = OUTCOME_LABEL[policy.outcome]
  return (
    <>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="check__head">
          <span className="checks__outcome">{t(outcomeKey)}</span>
          {policy.thresholds_are_examples && (
            <span className="policy__example">{t('policy.exampleThresholds')}</span>
          )}
        </p>
      </div>
      <p className="analysis__meta">
        {t('policy.evaluated', { date: formatDate(policy.evaluated_at) })}
      </p>

      <div className="policy__table-wrap">
        <table className="policy__table">
          <caption className="orchestration__stage-title">{t('policy.caption')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('policy.column.rule')}</th>
              <th scope="col">{t('policy.column.actual')}</th>
              <th scope="col">{t('policy.column.threshold')}</th>
              <th scope="col">{t('policy.column.verdict')}</th>
              <th scope="col">{t('policy.column.reason')}</th>
            </tr>
          </thead>
          <tbody>
            {policy.rules.map((rule) => {
              const { key: verdictKey, tone: verdictTone } = VERDICT_LABEL[rule.verdict]
              return (
                <tr key={rule.code}>
                  <th scope="row">{t(RULE_LABEL[rule.code])}</th>
                  <td>{ruleAmount(rule, rule.actual)}</td>
                  <td>{thresholdText(rule, t)}</td>
                  <td>
                    <span className={`check__status check__status--${verdictTone}`}>
                      {t(verdictKey)}
                    </span>
                  </td>
                  <td>{rule.reason}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default PolicySection
