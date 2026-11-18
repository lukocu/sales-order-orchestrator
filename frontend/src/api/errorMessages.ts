import type { ParseKeys, TFunction } from 'i18next'
import { ApiError, isAbortError, type ErrorParams } from './client'

export type ErrorOperation = 'read' | 'write' | 'login'
export type ErrorDescriptor =
  | { kind: 'api'; code: string; status: number | null; params: ErrorParams; operation: ErrorOperation }
  | { kind: 'local'; key: ParseKeys; params?: ErrorParams }

export function localError(key: ParseKeys, params?: ErrorParams): ErrorDescriptor {
  return { kind: 'local', key, params }
}

export function describeError(error: unknown, operation: ErrorOperation = 'read'): ErrorDescriptor | null {
  if (isAbortError(error)) return null
  return error instanceof ApiError
    ? { kind: 'api', code: error.code, status: error.status, params: error.params, operation }
    : { kind: 'api', code: 'UNKNOWN_ERROR', status: null, params: {}, operation }
}

const MESSAGE_KEYS = {
  NOT_AUTHENTICATED: 'apiErrors.session', INVALID_CREDENTIALS: 'apiErrors.credentials',
  SUPERVISOR_REQUIRED: 'apiErrors.permission', FORBIDDEN: 'apiErrors.permission',
  INQUIRY_NOT_FOUND: 'apiErrors.inquiryMissing', RUN_NOT_FOUND: 'apiErrors.resourceMissing',
  NO_ANALYSIS: 'apiErrors.analysisMissing', NOT_FOUND: 'apiErrors.resourceMissing',
  VALIDATION_ERROR: 'apiErrors.validation', INVALID_EDIT: 'apiErrors.invalidEdit',
  REASON_REQUIRED: 'apiErrors.reasonRequired',
  ANALYSIS_CHANGED: 'apiErrors.changed', INQUIRY_CHANGED: 'apiErrors.changed',
  DRAFT_CHANGED: 'apiErrors.changed', AWAITING_SUPERVISOR: 'apiErrors.awaiting',
  DRAFT_DECIDED: 'apiErrors.decided', DRAFT_NOT_EDITABLE: 'apiErrors.notEditable',
  DRAFT_STALE: 'apiErrors.stale', POLICY_MISSING: 'apiErrors.policyMissing',
  NOT_AWAITING_SUPERVISOR: 'apiErrors.notAwaiting', OWN_SUBMISSION: 'apiErrors.ownSubmission',
  NOTHING_TO_ORCHESTRATE: 'apiErrors.prerequisite', NOTHING_TO_RECOMMEND: 'apiErrors.prerequisite',
  NOTHING_TO_EVALUATE: 'apiErrors.prerequisite', NOTHING_TO_DRAFT: 'apiErrors.prerequisite',
  ANALYSIS_NOT_CONFIGURED: 'apiErrors.configuration', MAILBOX_NOT_CONFIGURED: 'apiErrors.configuration',
  MAILBOX_AUTH_FAILED: 'apiErrors.configuration',
  LOGIN_BUSY: 'apiErrors.busy', MAILBOX_BUSY: 'apiErrors.mailboxBusy',
  RATE_LIMITED: 'apiErrors.rateLimited', ANALYSIS_RATE_LIMITED: 'apiErrors.rateLimited',
  DATABASE_UNAVAILABLE: 'apiErrors.unavailable', MAILBOX_UNAVAILABLE: 'apiErrors.mailboxUnavailable',
  MAILBOX_ERROR: 'apiErrors.mailboxUnavailable',
  STORED_ANALYSIS_INVALID: 'apiErrors.storedInvalid',
  CHECKS_FAILED: 'apiErrors.processingFailed', ORCHESTRATION_FAILED: 'apiErrors.processingFailed',
  RECOMMENDATION_FAILED: 'apiErrors.processingFailed', POLICY_FAILED: 'apiErrors.processingFailed',
  DRAFT_FAILED: 'apiErrors.processingFailed', DECISION_FAILED: 'apiErrors.processingFailed',
  ANALYSIS_FAILED: 'apiErrors.processingFailed',
  NETWORK_ERROR: 'apiErrors.network', INVALID_RESPONSE: 'apiErrors.invalidResponse',
  INTERNAL_ERROR: 'apiErrors.generic', HTTP_ERROR: 'apiErrors.generic',
  METHOD_NOT_ALLOWED: 'apiErrors.generic', UNKNOWN_ERROR: 'apiErrors.generic',
} as const satisfies Record<string, ParseKeys>

const UNCERTAIN_CODES = new Set([
  'NETWORK_ERROR', 'INVALID_RESPONSE', 'INTERNAL_ERROR', 'HTTP_ERROR', 'UNKNOWN_ERROR',
  'DATABASE_UNAVAILABLE', 'DECISION_FAILED', 'CHECKS_FAILED', 'ORCHESTRATION_FAILED',
  'RECOMMENDATION_FAILED', 'POLICY_FAILED', 'DRAFT_FAILED', 'ANALYSIS_FAILED',
])

function isDescriptor(value: unknown): value is ErrorDescriptor {
  if (typeof value !== 'object' || value === null) return false
  const object = value as Record<string, unknown>
  return (object.kind === 'api' && typeof object.code === 'string' && typeof object.operation === 'string') ||
    (object.kind === 'local' && typeof object.key === 'string')
}

// Only trusted local keys and the allow-listed code table can reach t(). API params,
// diagnostic messages and unknown codes are never rendered as arbitrary text.
export function errorMessage(error: unknown, t: TFunction, operation: ErrorOperation = 'read'): string {
  const descriptor = isDescriptor(error) ? error : describeError(error, operation)
  if (descriptor === null) return ''
  if (descriptor.kind === 'local') return t(descriptor.key, descriptor.params ?? {})
  const known = Object.hasOwn(MESSAGE_KEYS, descriptor.code)
  const key = known ? MESSAGE_KEYS[descriptor.code as keyof typeof MESSAGE_KEYS] : 'apiErrors.generic'
  const uncertain = descriptor.operation === 'write' &&
    (UNCERTAIN_CODES.has(descriptor.code) || !known)
  return uncertain ? t('apiErrors.writeUncertain') : t(key)
}
