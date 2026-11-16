import { useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { PolicyResult, PolicyView, RecommendationView, ReplyDraftView } from '../api/analysis'
import { UnauthorizedError } from '../api/client'
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate } from './format'
import {
  OUTCOME_LABEL,
  policyRerunOffered,
  RULE_LABEL,
  ruleAmount,
  thresholdText,
  VERDICT_LABEL,
} from './policyLabels'

type Props = {
  inquiryId: number
  // null while there is no verdict for the current recommendation.
  policy: PolicyView | null
  // The recommendation the verdict is evaluated on; tells why there is none.
  recommendation: RecommendationView | null
  // The reply draft, when there is one: its stored verdict is the one in force (the offer may
  // have been edited), so that one is shown instead of the evaluation.
  draft?: ReplyDraftView | null
  // True when re-running the policy is the step's primary action (outline otherwise).
  primary?: boolean
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
  draft = null,
  primary = false,
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
  const offerRerun = policyRerunOffered(policy, recommendation)

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
          <Button
            type="button"
            variant={primary ? 'default' : 'outline'}
            onClick={rerun}
            disabled={disabled}
          >
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

      {draft !== null ? (
        <VerdictOfDraft policy={draft.policy} edited={draft.offer.edited} />
      ) : (
        policy !== null && <Evaluation policy={policy} />
      )}
    </section>
  )
}

// Each rule against its threshold.
function RulesTable({ rules, caption }: { rules: PolicyResult['rules']; caption: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="policy__table-wrap">
      <table className="policy__table">
        <caption className="orchestration__stage-title">{caption}</caption>
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
          {rules.map((rule) => {
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
  )
}

// The policy stage's own evaluation of the recommended option.
function Evaluation({ policy }: { policy: PolicyView }) {
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
      <RulesTable rules={policy.rules} caption={t('policy.caption')} />
    </>
  )
}

// The verdict stored with the draft: the edit's own for an edited offer, the evaluation's
// otherwise.
function VerdictOfDraft({ policy, edited }: { policy: PolicyResult | null; edited: boolean }) {
  const { t } = useTranslation()
  const title = edited ? t('draft.verdictTitleEdited') : t('draft.verdictTitle')
  if (policy === null) {
    return <p className="checks__line">{t('draft.verdictNone', { title })}</p>
  }
  const { key: outcomeKey, tone } = OUTCOME_LABEL[policy.outcome]
  return (
    <>
      {policy.thresholds_are_examples && (
        <p className="policy__example">{t('policy.exampleThresholds')}</p>
      )}
      <RulesTable
        rules={policy.rules}
        caption={
          <>
            {t('draft.verdictLabel', { title })}{' '}
            <span className={`check__status check__status--${tone}`}>{t(outcomeKey)}</span>
          </>
        }
      />
    </>
  )
}

export default PolicySection
