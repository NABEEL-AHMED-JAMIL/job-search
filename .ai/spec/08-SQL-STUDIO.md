# SQL Studio

## Layout
- left: dataset/schema browser
- center: SQL editor
- bottom: result grid
- right: query metadata/help

## Features
- Monaco editor
- syntax highlighting
- autocomplete
- schema/table suggestions
- formatting
- run
- cancel
- explain/preview where safe
- query history
- saved queries

## Result grid
- server pagination
- column resize
- sorting where supported
- download/export
- execution time
- rows returned
- warnings

## Query states
Draft, Running, Completed, Failed, Cancelled, Timed Out.

## Security
The backend validates authorization for every referenced dataset. Do not rely on UI restrictions.

## Query history
Persist:
- query ID
- tenant
- user
- query text or protected representation according to security policy
- datasets
- duration
- status
- timestamp
- error class

Never persist secrets accidentally included in query text.
