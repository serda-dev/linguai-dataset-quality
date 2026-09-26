Feature: Isolated authenticated teacher inference and replacement
  The persistent VPS is the source of truth; the GPU host is disposable.

  Scenario: A request has no valid service credential
    Given a nonempty runtime API credential is configured
    When an unauthenticated or incorrectly authenticated client requests inference
    Then the service denies the request before model execution
    And it does not echo the document, secret or prompt in the response or logs

  Scenario: The service is reached from the VPS
    Given the GPU instance exposes a selected inference port
    When the VPS worker connects to the endpoint
    Then the path uses an authenticated encrypted transport or a private encrypted tunnel
    And the Jupyter interface is not used as a substitute for the inference API

  Scenario: The teacher process stops during a request
    Given a persisted claim and in-flight attempt on the VPS
    When the GPU process crashes or its network path disappears
    Then the client receives a timeout or controlled non-success response
    And the VPS retains the document and retryable job state
    And the GPU host cannot commit a label directly to the VPS database

  Scenario: A replacement GPU endpoint is activated
    Given pending VPS jobs and a new reachable inference endpoint
    When the worker is restarted with a new runtime teacher profile and endpoint
    Then pending jobs can be retried through the new endpoint
    And earlier attempts keep their original model/profile/endpoint fingerprint
    And already accepted labels are not overwritten

  Scenario: The endpoint receives several bounded requests
    Given measured concurrency and input-token limits for this GPU profile
    When requests exceed those limits
    Then admission is bounded and excess requests fail or wait with a documented status
    And the process does not corrupt other responses or silently return a partial JSON label

  Scenario: Operational logs are inspected
    Given successful, rejected and timed-out document requests
    When service logs and notebook output are reviewed
    Then no raw document, complete prompt payload, API credential or generated label body is present
    And job correlation uses only non-sensitive identifiers or redacted hashes
