Feature: Docker-gated deployment
  Scenario: Pre-deploy test failure
    Given a candidate commit failing isolated Docker tests
    When deployment is evaluated
    Then main is not deployed to the new production project

  Scenario: Production smoke without teacher workload
    Given a successfully deployed API and worker
    When the read-only smoke checks run
    Then health, readiness, database, worker, artifact path and teacher profile are verified
    And no labeling job is created

  Scenario: Full teacher run needs approval
    Given a configured 40k run
    When no explicit user authorization exists
    Then the run cannot be started


  Scenario: Deploy before renting the teacher GPU
    Given valid database and admin credentials and empty teacher configuration
    When the production Compose stack starts
    Then initialization needs only database configuration
    And the API health endpoint succeeds and the worker remains idle
    And readiness and run activation remain unavailable
    And no document is claimed or retry budget consumed

  Scenario: Connect the configured teacher later
    Given the deployed control plane and a measured teacher endpoint
    When endpoint, model and profile are set and API and worker containers are recreated
    Then the existing readiness checks can succeed
    And only explicitly activated approved runs may be claimed
