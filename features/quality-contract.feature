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

  Scenario: Excellent Turkish article is eligible for premium
    Given a general article with high independent language, coherence, information, cleanliness, structure and utility scores
    When policy version 1 routes the label
    Then the route is PREMIUM

  Scenario: Meaningful table or mathematical reference is not punished as prose
    Given a structured_data label with null natural-language score and high information and structure
    Then the label is valid and can route to KEEP

  Scenario: Fluent SEO filler has little learning signal
    Given a general label with language 4 but information 1, cleanliness 1 and utility 1
    Then the route is DROP

  Scenario: Natural forum discussion remains useful
    Given a conversation label with good language and utility but modest factual information
    Then the route is KEEP

  Scenario: Unrelated fragments are not trained as coherent prose
    Given a noise_unknown label with coherence 0, structure 0 and utility 0
    Then the route is DROP

  Scenario: Information-rich OCR damage remains a repair candidate
    Given a reference label with information 4, cleanliness 1, coherence 2 and encoding_ocr noise
    Then the route is MODEL_REPAIR
