Feature: Explicitly approved, bounded corpus processing
  Scenario: Full-run threshold cannot be bypassed with multiple runs
    Given 39999 unapproved jobs were reserved across runs
    When the admin reserves one more without a full-run approval credential
    Then the reservation is denied and no job or approval record changes

  Scenario: Streaming order changes during resume
    Given an interrupted source run with a persisted prefix digest
    When replay at the same revision yields a different prefix
    Then ingestion fails closed without queueing teacher jobs

  Scenario: Valuable structured original is preserved
    Given a source record containing a meaningful JSON document
    When it is selected for teacher review
    Then the original text and its format flag remain separate from the teacher label

  Scenario: Bounded export has no accidental evaluation split
    Given accepted labels without an approved split policy
    When a Parquet export is created
    Then all envelopes belong to train and exact duplicate families have one group identifier

  Scenario: Teacher attempt fails before response
    Given a claimed job with a persisted attempt start
    When the teacher times out or emits invalid JSON
    Then the attempt records its failure class without raw document content
    And the job remains retryable up to its bounded limit
