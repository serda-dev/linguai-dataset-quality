Feature: Preserve independent teacher observations and routing
  Scenario: Valuable noisy web text is eligible for deterministic repair
    Given an exact-schema label with information 4, cleanliness 1, utility 3 and boilerplate_ui noise
    When policy version 1 routes the label
    Then the route is DETERMINISTIC_REPAIR
    And the teacher label remains unchanged

  Scenario: Structured code without natural language remains eligible
    Given a label of type code with language null, information 4, structure 4 and utility 4
    Then the response passes teacher schema validation

  Scenario: Teacher returns a different document ID
    Given a request for document A
    When the teacher returns a valid-schema label for document B
    Then the response is rejected and no label is accepted
