import { useTranslation } from 'react-i18next'
import type { ReplyDraftDecision, ReplyDraftView } from '../api/analysis'
import { ACTION_KEY, STATUS } from './draftLabels'
import { DraftEmail } from './ReplyDraftSection'
import { formatDate } from './format'

type Props = {
  inquiryId: number
  // The draft that is ready to send; null while there is none.
  draft: ReplyDraftView | null
  // Every decision on the inquiry's drafts, oldest first; the last one made the draft ready.
  decisions: ReplyDraftDecision[]
}

// The result of the flow: the final e-mail and who approved it. Nothing is sent (sending is
// simulated) and there is nothing left to decide, so the step has no action.
function ReplyStep({ inquiryId, draft, decisions }: Props) {
  const { t } = useTranslation()
  const headingId = `reply-${inquiryId}-heading`
  if (draft === null) return null
  const [statusKey, tone] = STATUS[draft.status]
  const last = decisions.length > 0 ? decisions[decisions.length - 1] : null
  return (
    <section className="orchestration" aria-labelledby={headingId}>
      <h4 id={headingId} className="analysis__subheading">
        {t('reply.heading')}
      </h4>
      <div className={`checks__banner orchestration__banner--${tone}`}>
        <p className="checks__outcome">
          {t('draft.statusLabel')} <span className="draft__status">{t(statusKey)}</span>
        </p>
      </div>
      {last !== null && (
        <dl className="metrics__list" aria-label={t('reply.decision')}>
          <dt>{t('reply.decision')}</dt>
          <dd>{t(ACTION_KEY[last.action])}</dd>
          <dt>{t('decisionHistory.by')}</dt>
          <dd>{last.decided_by_name ?? t('decisionHistory.unknownUser')}</dd>
          <dt>{t('decisionHistory.when')}</dt>
          <dd>{formatDate(last.decided_at)}</dd>
        </dl>
      )}
      <DraftEmail draft={draft} />
    </section>
  )
}

export default ReplyStep
