Feature: Replaceable resumable teacher jobs
  Scenario: Worker crashes during a claim
    Given a persisted job claimed by a worker
    When the worker stops before committing a validated result
    Then another worker can reclaim the expired lease
    And at most one accepted label per document and labeling contract is committed

  Scenario: Teacher returns invalid JSON
    Given a mock teacher returning malformed JSON
    When the worker processes the job
    Then it records a bounded retryable failure
    And it does not store an accepted label

  Scenario: Endpoint replacement
    Given persisted pending jobs
    When the external teacher endpoint is replaced
    Then pending jobs continue through a new teacher profile
    And previous attempts retain their original profile provenance
