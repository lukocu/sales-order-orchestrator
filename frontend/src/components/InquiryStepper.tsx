import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { STEP_ORDER, type InquirySteps as StepModel, type StepId } from './inquirySteps'

type Props = {
  steps: StepModel
  // The step whose panel is shown; a step that is locked or not needed cannot be viewed.
  viewed: StepId
  onView: (step: StepId) => void
  // The content of each step; only the viewed step's panel is mounted.
  panels: Record<StepId, ReactNode>
}

// The step bar and the panel of the viewed step. Every state is written out as text, so the
// bar never relies on colour alone.
function InquiryStepper({ steps, viewed, onView, panels }: Props) {
  const { t } = useTranslation()
  return (
    <Tabs value={viewed} onValueChange={(value) => onView(value as StepId)} className="gap-3">
      <TabsList
        aria-label={t('steps.label')}
        className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-4 group-data-[orientation=horizontal]/tabs:h-auto"
      >
        {STEP_ORDER.map((step, index) => {
          const state = steps.states[step]
          return (
            <TabsTrigger
              key={step}
              value={step}
              disabled={state === 'locked' || state === 'not_needed'}
              className="h-auto flex-col items-start gap-0 whitespace-normal py-1.5 text-left"
            >
              <span className="font-semibold">
                {index + 1}. {t(`steps.names.${step}`)}
              </span>{' '}
              <span className="text-xs font-normal">{t(`steps.state.${state}`)}</span>
            </TabsTrigger>
          )
        })}
      </TabsList>
      {STEP_ORDER.map((step) => (
        <TabsContent key={step} value={step} className="grid min-w-0 gap-3">
          {panels[step]}
        </TabsContent>
      ))}
    </Tabs>
  )
}

export default InquiryStepper
