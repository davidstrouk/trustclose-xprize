-- BigQuery: the agent_decisions evidence trail (AI-Native-Operations audit).
-- One row per questionnaire question the agent answered or deferred.
CREATE TABLE IF NOT EXISTS `trustclose.agent_decisions` (
  run_id      STRING,
  customer_id STRING,
  row         INT64,
  question    STRING,
  action      STRING,    -- 'answer' | 'defer'
  answer      STRING,
  citation    STRING,
  confidence  FLOAT64,
  created_at  TIMESTAMP
);
