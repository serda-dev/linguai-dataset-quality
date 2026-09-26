Feature: Small approved teacher rubric calibration
  A model must demonstrate semantic label behavior before any large labeling run.

  Background:
    Given the exact turkish_cpt_quality_teacher_v2 system prompt
    And the teacher_label_v1 response schema
    And a small human-reviewed calibration set explicitly approved for inference

  Scenario: High-quality Turkish prose
    When the teacher labels a coherent informative clean Turkish article
    Then language, coherence, information, cleanliness, structure and utility are high

  Scenario: Valuable article contaminated by web boilerplate
    When the teacher labels an informative article with material menu and cookie debris
    Then information remains high and cleanliness is lower
    And boilerplate_ui is present when the debris is material
    And the teacher returns no KEEP or DROP decision

  Scenario: Meaningful code with essentially no natural language
    When the teacher labels intact source code without natural-language prose
    Then type is code and language may be null
    And information and structure can remain high

  Scenario: Meaningful structured reference
    When the teacher labels an intact table, formula or structured reference
    Then the non-prose format does not by itself force low utility or structure

  Scenario: Fluent SEO filler
    When the teacher labels fluent but repetitive advertising filler
    Then good language does not force high information or cleanliness

  Scenario: Natural forum conversation
    When the teacher labels a coherent, useful informal forum conversation
    Then its informal register alone does not lower utility

  Scenario: Random unrelated fragments
    When the teacher labels a concatenation of unrelated fragments
    Then coherence and utility are low and unrelated_merge is flagged when material

  Scenario: Information-rich OCR corruption
    When the teacher labels a source with valuable content but material OCR damage
    Then information can remain high while cleanliness and language fall
    And encoding_ocr is present when the damage is material

  Scenario: Calibration exceeds the approved scope
    Given no authorization for a full 40k teacher run
    When the approved small calibration count is reached
    Then no further real inference is started by setup, health checks or this feature suite
