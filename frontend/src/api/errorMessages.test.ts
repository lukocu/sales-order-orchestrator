import { describe, expect, it } from 'vitest'
import i18n from '../i18n'
import { ApiError, UnauthorizedError } from './client'
import { describeError, errorMessage, localError } from './errorMessages'

const GROUPS = {
  session: ['NOT_AUTHENTICATED'], credentials: ['INVALID_CREDENTIALS'],
  permission: ['SUPERVISOR_REQUIRED', 'FORBIDDEN'],
  inquiryMissing: ['INQUIRY_NOT_FOUND'], resourceMissing: ['RUN_NOT_FOUND', 'NOT_FOUND'],
  analysisMissing: ['NO_ANALYSIS'], validation: ['VALIDATION_ERROR'], invalidEdit: ['INVALID_EDIT'],
  reasonRequired: ['REASON_REQUIRED'], changed: ['ANALYSIS_CHANGED', 'INQUIRY_CHANGED', 'DRAFT_CHANGED'],
  awaiting: ['AWAITING_SUPERVISOR'], decided: ['DRAFT_DECIDED'], notEditable: ['DRAFT_NOT_EDITABLE'],
  stale: ['DRAFT_STALE'], policyMissing: ['POLICY_MISSING'], notAwaiting: ['NOT_AWAITING_SUPERVISOR'],
  ownSubmission: ['OWN_SUBMISSION'],
  prerequisite: ['NOTHING_TO_ORCHESTRATE', 'NOTHING_TO_RECOMMEND', 'NOTHING_TO_EVALUATE', 'NOTHING_TO_DRAFT'],
  configuration: ['ANALYSIS_NOT_CONFIGURED', 'MAILBOX_NOT_CONFIGURED', 'MAILBOX_AUTH_FAILED'],
  busy: ['LOGIN_BUSY'], mailboxBusy: ['MAILBOX_BUSY'], rateLimited: ['RATE_LIMITED', 'ANALYSIS_RATE_LIMITED'],
  unavailable: ['DATABASE_UNAVAILABLE'], mailboxUnavailable: ['MAILBOX_UNAVAILABLE', 'MAILBOX_ERROR'],
  storedInvalid: ['STORED_ANALYSIS_INVALID'],
  processingFailed: ['CHECKS_FAILED', 'ORCHESTRATION_FAILED', 'RECOMMENDATION_FAILED', 'POLICY_FAILED', 'DRAFT_FAILED', 'DECISION_FAILED', 'ANALYSIS_FAILED'],
  network: ['NETWORK_ERROR'], invalidResponse: ['INVALID_RESPONSE'],
  generic: ['INTERNAL_ERROR', 'HTTP_ERROR', 'METHOD_NOT_ALLOWED', 'UNKNOWN_ERROR'],
} as const

describe('render-time error messages', () => {
  it.each(['pl', 'en'])('translates every backend code group in %s', async (language) => {
    await i18n.changeLanguage(language)
    for (const [key, codes] of Object.entries(GROUPS)) for (const code of codes) {
      const message = errorMessage(new ApiError('PRIVATE SQL JSON HTTP exception', 500, code), i18n.t)
      expect(message).toBe(i18n.t(`apiErrors.${key as keyof typeof GROUPS}`))
      expect(message).not.toMatch(/PRIVATE|SQL|JSON|HTTP|undefined|null/)
    }
  })

  it('retranslates a stored descriptor and preserves local validation parameters', async () => {
    const api = describeError(new ApiError('private', 403, 'SUPERVISOR_REQUIRED'))
    const local = localError('draft.form.quantityWhole')
    const english = errorMessage(api, i18n.t)
    await i18n.changeLanguage('pl')
    expect(errorMessage(api, i18n.t)).not.toBe(english)
    expect(errorMessage(local, i18n.t)).toBe(i18n.t('draft.form.quantityWhole'))
  })

  it('distinguishes login from expired session', () => {
    expect(errorMessage(describeError(new UnauthorizedError('Invalid username or password'), 'login'), i18n.t)).toBe(i18n.t('apiErrors.credentials'))
    expect(errorMessage(new UnauthorizedError(), i18n.t)).toBe(i18n.t('apiErrors.session'))
  })

  it.each(['NETWORK_ERROR', 'INVALID_RESPONSE', 'INTERNAL_ERROR', 'DATABASE_UNAVAILABLE', 'DECISION_FAILED', 'FUTURE_CODE'])('requires checking state after an uncertain write: %s', (code) => {
    const error = new ApiError('private', 500, code)
    expect(errorMessage(describeError(error, 'write'), i18n.t)).toBe(i18n.t('apiErrors.writeUncertain'))
    expect(errorMessage(describeError(error, 'read'), i18n.t)).not.toBe(i18n.t('apiErrors.writeUncertain'))
  })

  it.each(['SUPERVISOR_REQUIRED', 'VALIDATION_ERROR', 'DRAFT_CHANGED', 'OWN_SUBMISSION'])('retains a definite refusal explanation for %s', (code) => {
    const error = new ApiError('private', 409, code)
    expect(errorMessage(error, i18n.t, 'write')).toBe(errorMessage(error, i18n.t, 'read'))
    expect(errorMessage(error, i18n.t, 'write')).not.toBe(i18n.t('apiErrors.writeUncertain'))
  })

  it('keeps arbitrary errors and unknown code params out of the UI', () => {
    expect(errorMessage(new Error('private password'), i18n.t)).toBe(i18n.t('apiErrors.generic'))
    expect(errorMessage(new ApiError('private', 401, 'FUTURE_CODE', { password: 'private' }), i18n.t)).toBe(i18n.t('apiErrors.generic'))
  })
})
