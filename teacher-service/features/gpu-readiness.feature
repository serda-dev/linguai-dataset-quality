Feature: Measured readiness of an ephemeral 48 GB GPU teacher
  Readiness proves that the selected model can serve bounded requests on the actual instance.

  Scenario: The Jupyter SSH instance has GPU access but no inference server
    Given SSH access and a reported 48 GB VRAM GPU
    When the service process or model is not loaded
    Then liveness may report the host process as alive
    But readiness reports unavailable and the control plane does not enqueue a probe label

  Scenario: The chosen model does not fit the measured GPU budget
    Given actual GPU memory free, model revision, context length and concurrency settings
    When model loading or one bounded representative request runs out of memory
    Then readiness remains unavailable
    And setup records the failed profile without claiming that 48 GB alone guarantees fit

  Scenario: Model loading completes and the API is ready
    Given a pinned model revision and recorded serving engine version
    When weights and runtime initialization complete
    Then a non-labeling health check succeeds
    And a model-list or equivalent readiness check reports the selected model identifier
    And the configured endpoint is reachable from the VPS over the approved transport

  Scenario: The measured response exceeds the current caller deadline
    Given a representative document sketch under the approved input bound
    When p95 latency exceeds the current 20-second caller timeout
    Then the profile is not accepted for live teacher jobs
    And the caller timeout, concurrency or model profile must be changed and retested explicitly

  Scenario: Readiness probing is non-destructive
    Given a newly started GPU service
    When the deployment and health probes run
    Then no source dataset is fetched
    And no labeling job, accepted label or repair artifact is created
