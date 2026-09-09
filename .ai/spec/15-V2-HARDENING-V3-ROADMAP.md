# V2 Hardening & V3 Roadmap

## V2 — Hardening
After the first implementation is working, perform:

### Architecture
- remove duplicated services
- simplify abstractions
- verify dependency boundaries
- inspect query plans

### Security
- penetration-style authorization tests
- secret scanning
- tenant-isolation review
- audit completeness

### UX
- visual consistency
- accessibility
- keyboard navigation
- responsive behavior
- loading/error/empty states
- dense data-table ergonomics

### Performance
- benchmark regression suite
- profile expensive queries
- optimize high-cardinality analytics
- verify cancellation
- optimize storage reads

### Reliability
- retry policy for transient storage errors
- idempotent export/write operations
- cleanup of temporary resources

## V3 — Future analytics
Potential additions:
- natural-language-to-SQL
- AI explanations of profile results
- anomaly detection
- automatic chart recommendations
- semantic dataset catalog
- lineage
- data contracts
- scheduled analytical reports
- alerts
- collaborative dashboards

AI features must remain optional and must obey existing authorization.
