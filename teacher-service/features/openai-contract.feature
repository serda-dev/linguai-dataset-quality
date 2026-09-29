Feature: OpenAI-compatible quality teacher boundary
  The GPU service implements the existing control-plane request and reply contract.

  Scenario: The control plane requests one label
    Given the service is ready with a configured model identifier
    And the request contains exactly a system message with the versioned teacher prompt
    And a user message containing DOCUMENT_ID and the document sketch, without source dataset metadata
    When an authorized client POSTs to /v1/chat/completions with temperature 0
    Then the response contains choices[0].message.content as a string
    And that string parses as one JSON object conforming to teacher_label_v1.schema.json
    And the response id equals the supplied DOCUMENT_ID
    And the teacher JSON contains no routing, provenance, explanation or reasoning fields

  Scenario: The model produces extra prose or a fenced JSON block
    Given the raw generation contains prose, a code fence or a reasoning trace
    When the service prepares the completion response
    Then it never reports that generation as a successful valid teacher label
    And it returns a controlled failure or regenerates within a bounded configured limit

  Scenario: The model produces a schema-valid label for another document
    Given the request identifies document A
    When the model returns an otherwise valid label identifying document B
    Then the service fails that inference request
    And no corrected id is fabricated by replacing B with A

  Scenario: The caller uses an unsupported model identifier
    Given the service exposes one selected versioned model identifier
    When a request names a different model
    Then the service returns a controlled client error before inference

  Scenario: The request is malformed or exceeds its configured input bound
    Given the incoming messages omit the document id or exceed the measured context budget
    When the request is validated
    Then inference does not start
    And the service returns a controlled non-success status without echoing the document

  Scenario: A backend can optionally constrain JSON generation
    Given the selected serving engine supports structured JSON output
    When the engine is configured for teacher_label_v1.schema.json
    Then the caller's existing request shape still succeeds without provider-specific parameters
    And the completed response is independently validated before returning success
