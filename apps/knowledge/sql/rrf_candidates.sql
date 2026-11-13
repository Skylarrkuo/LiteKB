WITH eligible AS NOT MATERIALIZED (
    SELECT e.id, e.paragraph_id, e.embedding, e.search_vector
    FROM embedding e
    JOIN document d ON d.id = e.document_id AND d.knowledge_id = e.knowledge_id AND d.is_active
    JOIN paragraph p ON p.id = e.paragraph_id AND p.knowledge_id = e.knowledge_id
                    AND p.document_id = e.document_id AND p.is_active
    WHERE e.knowledge_id = %s AND e.is_active AND vector_dims(e.embedding) = %s
      AND COALESCE(e.document_id = ANY(array_remove(%s::uuid[], NULL)), true)
      AND NOT (e.document_id = ANY(array_remove(%s::uuid[], NULL)))
      AND NOT (e.paragraph_id = ANY(array_remove(%s::uuid[], NULL)))
), q AS (
    SELECT websearch_to_tsquery('simple', %s) AS terms
), dense AS MATERIALIZED (
    SELECT paragraph_id, search_vector, embedding::vector(%s) <=> %s AS distance
    FROM eligible
    ORDER BY distance
    LIMIT %s
), lexical AS MATERIALIZED (
    SELECT paragraph_id, embedding, ts_rank_cd(search_vector, q.terms, 32) AS lexical_score
    FROM eligible CROSS JOIN q
    WHERE search_vector @@ q.terms
    ORDER BY lexical_score DESC, id
    LIMIT %s
)
SELECT paragraph_id, 'dense' AS branch, 1 - distance AS dense_score,
       COALESCE(ts_rank_cd(search_vector, q.terms, 32), 0) AS lexical_score
FROM dense CROSS JOIN q
UNION ALL
SELECT paragraph_id, 'lexical' AS branch, 1 - (embedding <=> %s) AS dense_score, lexical_score
FROM lexical
