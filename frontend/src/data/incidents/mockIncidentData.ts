import {
  IncidentSeverity,
  IncidentStatus,
  IncidentType,
  type Incident,
} from '../../types/incident'

/**
 * Operational incident mock data. Isolated from live run/payment/investigation
 * APIs. Related IDs here are mock-only and must not be mixed with backend data.
 */
export const MOCK_INCIDENTS: Incident[] = [
  {
    incident_id: 'INC-2026-0142',
    title: 'Missing bank credit backlog',
    summary:
      'Multiple batches remain without a matching bank credit after the expected settlement window. Operations is treating this as a single credit-gap incident rather than isolated exceptions.',
    severity: IncidentSeverity.CRITICAL,
    status: IncidentStatus.OPEN,
    type: IncidentType.BANK_CREDIT_GAP,
    affected_exception_count: 28,
    affected_payment_count: 41,
    impact_paise: 87634000,
    last_updated: '2026-09-04T16:22:00+05:30',
    opened_at: '2026-09-03T09:10:00+05:30',
    owner: 'Settlements desk',
    window: '2–4 Sept 2026 settlement cycle',
    notes:
      'Hold payouts tied to the affected batches until bank credits land. Do not reclassify individual exceptions until the credit file is confirmed.',
    exception_types: ['Missing bank credit'],
    related_investigation_ids: [
      'EXC-BATCH-batch_1108',
      'EXC-BATCH-batch_1184',
      'EXC-BATCH-batch_1312',
    ],
  },
  {
    incident_id: 'INC-2026-0148',
    title: 'High-value amount variance cluster',
    summary:
      'Several payment and batch exceptions share the same amount-mismatch pattern against settlement credits. The variances are consistent enough to investigate as one operational cluster.',
    severity: IncidentSeverity.HIGH,
    status: IncidentStatus.INVESTIGATING,
    type: IncidentType.AMOUNT_VARIANCE_CLUSTER,
    affected_exception_count: 42,
    affected_payment_count: 57,
    impact_paise: 24560000,
    last_updated: '2026-09-04T15:48:00+05:30',
    opened_at: '2026-09-03T18:40:00+05:30',
    owner: 'Reconciliation ops',
    window: '3–4 Sept 2026',
    notes:
      'Compare merchant-side fee deductions against settlement file versions. Related investigations remain authoritative for each exception.',
    exception_types: ['Amount mismatch'],
    related_investigation_ids: [
      'EXC-BATCH-batch_1042',
      'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL',
      'EXC-BATCH-batch_1203',
      'EXC-BATCH-batch_1330',
      'EXC-BATCH-batch_1401',
    ],
  },
  {
    incident_id: 'INC-2026-0151',
    title: 'Unmatched settlement references',
    summary:
      'UTR and bank-reference mismatches are concentrated in one acquirer file. Individual investigations exist; this incident tracks the file-level matching failure.',
    severity: IncidentSeverity.MEDIUM,
    status: IncidentStatus.OPEN,
    type: IncidentType.REFERENCE_MISMATCH_CLUSTER,
    affected_exception_count: 8,
    affected_payment_count: 11,
    impact_paise: 6720000,
    last_updated: '2026-09-04T14:05:00+05:30',
    opened_at: '2026-09-04T11:20:00+05:30',
    owner: 'Bank ops',
    window: '4 Sept 2026 inbound file',
    notes:
      'Request a corrected UTR extract from the acquirer before expanding the investigation set.',
    exception_types: ['Unmatched reference'],
    related_investigation_ids: [
      'EXC-PAYMENT-pay_NrL9wK0yU3oSqM',
      'EXC-PAYMENT-pay_SwQ4bP5dZ8tXvS',
      'EXC-BATCH-batch_1090',
    ],
  },
  {
    incident_id: 'INC-2026-0137',
    title: 'Refund mismatch cycle',
    summary:
      'Refunds posted on the payment side are not lining up with settlement refund legs. The cycle has repeated across two days and is being tracked as one incident.',
    severity: IncidentSeverity.HIGH,
    status: IncidentStatus.INVESTIGATING,
    type: IncidentType.REFUND_CYCLE,
    affected_exception_count: 4,
    affected_payment_count: 6,
    impact_paise: 2450000,
    last_updated: '2026-09-04T13:12:00+05:30',
    opened_at: '2026-09-02T16:55:00+05:30',
    owner: 'Refunds desk',
    window: '2–4 Sept 2026 refunds',
    notes:
      'Confirm whether the acquirer is netting refunds inside the original capture settlement.',
    exception_types: ['Refund mismatch'],
    related_investigation_ids: [
      'EXC-PAYMENT-pay_OsM0xL1zV4pTrN',
      'EXC-PAYMENT-pay_PtN1yM2aW5qUsP',
    ],
  },
  {
    incident_id: 'INC-2026-0155',
    title: 'Unknown classification backlog',
    summary:
      'A small set of exceptions remains unclassified after the latest run. They are grouped here so operators can work them as one backlog rather than isolated unknowns.',
    severity: IncidentSeverity.LOW,
    status: IncidentStatus.OPEN,
    type: IncidentType.AMOUNT_VARIANCE_CLUSTER,
    affected_exception_count: 6,
    affected_payment_count: 8,
    impact_paise: 1890000,
    last_updated: '2026-09-04T12:30:00+05:30',
    opened_at: '2026-09-04T10:05:00+05:30',
    owner: 'Reconciliation ops',
    window: '4 Sept 2026 run',
    notes:
      'Keep deterministic_status as Unknown until supporting evidence is attached. Do not invent a classification.',
    exception_types: ['Unknown', 'Amount mismatch'],
    related_investigation_ids: [
      'EXC-PAYMENT-pay_QuO2zN3bX6rVtQ',
      'EXC-PAYMENT-pay_TxR5cQ6eA9uYwT',
      'EXC-PAYMENT-pay_RvP3aO4cY7sWuR',
    ],
  },
  {
    incident_id: 'INC-2026-0144',
    title: 'Cross-batch bank credit gap',
    summary:
      'Bank credits expected against two consecutive batches have not arrived. Impact overlaps the broader credit-gap incident and is kept separate because the batches share a single UTR expectation.',
    severity: IncidentSeverity.CRITICAL,
    status: IncidentStatus.INVESTIGATING,
    type: IncidentType.BANK_CREDIT_GAP,
    affected_exception_count: 9,
    affected_payment_count: 14,
    impact_paise: 104454000,
    last_updated: '2026-09-04T11:58:00+05:30',
    opened_at: '2026-09-03T21:15:00+05:30',
    owner: 'Settlements desk',
    window: '3 Sept late file + 4 Sept morning file',
    notes:
      'Coordinate with INC-2026-0142. Close this incident only after both batch credits are confirmed in the bank statement.',
    exception_types: ['Missing bank credit', 'Amount mismatch'],
    related_investigation_ids: [
      'EXC-BATCH-batch_1184',
      'EXC-BATCH-batch_1312',
      'EXC-PAYMENT-pay_MqK8vJ9xT2nRpL',
    ],
  },
  {
    incident_id: 'INC-2026-0129',
    title: 'Settlement window delay',
    summary:
      'The 1 Sept settlement file arrived after the expected cut-off, creating a short pending window. Bank credits subsequently matched and the incident was closed.',
    severity: IncidentSeverity.MEDIUM,
    status: IncidentStatus.RESOLVED,
    type: IncidentType.SETTLEMENT_DELAY,
    affected_exception_count: 11,
    affected_payment_count: 19,
    impact_paise: 4310000,
    last_updated: '2026-09-02T19:40:00+05:30',
    opened_at: '2026-09-01T22:10:00+05:30',
    owner: 'Settlements desk',
    window: '1–2 Sept 2026',
    notes:
      'Resolved after the delayed settlement file posted. No residual unmatched credits.',
    exception_types: ['Amount mismatch'],
    related_investigation_ids: [
      'EXC-BATCH-batch_1071',
      'EXC-BATCH-batch_1255',
    ],
  },
  {
    incident_id: 'INC-2026-0118',
    title: 'Contained refund variance',
    summary:
      'A single-day refund mismatch was isolated to two payments and closed after the acquirer posted the missing refund legs.',
    severity: IncidentSeverity.LOW,
    status: IncidentStatus.RESOLVED,
    type: IncidentType.REFUND_CYCLE,
    affected_exception_count: 2,
    affected_payment_count: 2,
    impact_paise: 890000,
    last_updated: '2026-08-31T17:05:00+05:30',
    opened_at: '2026-08-30T13:44:00+05:30',
    owner: 'Refunds desk',
    window: '30–31 Aug 2026',
    notes:
      'Closed. Related investigations remain in the queue for audit history only.',
    exception_types: ['Refund mismatch'],
    related_investigation_ids: ['EXC-PAYMENT-pay_OsM0xL1zV4pTrN'],
  },
]
