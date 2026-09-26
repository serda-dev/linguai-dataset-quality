Feature: Bounded reproducible source sampling
  Scenario: Stream without local corpus download
    Given an approved source adapter with a bounded streaming iterator
    When a sample run selects documents
    Then it records source revision and sampling seed for selected records
    And it never materializes the full source corpus locally

  Scenario: Interrupted source stream
    Given an interrupted source stream after persisted selections
    When the run resumes against the same pinned revision
    Then it does not duplicate persisted selections
    And it reports an explicit failure if the revision or ordering cannot be resumed safely
