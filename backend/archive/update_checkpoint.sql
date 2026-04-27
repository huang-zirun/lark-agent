UPDATE checkpoint_record
SET status = 'APPROVED',
    decision_by = 'tester',
    decision_at = CURRENT_TIMESTAMP,
    reason = '设计方案合理，同意继续'
WHERE id = 'b0494f36b34842bdaeb93851dd9053f6';
