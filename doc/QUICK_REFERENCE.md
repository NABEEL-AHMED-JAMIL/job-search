KAFKA LISTENERS - QUICK START GUIDE
==================================

## TL;DR

### Your Problem
```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

### What We Fixed
✅ Enhanced JSON deserialization to handle any message format
✅ Added robust error handling that won't crash on bad messages
✅ All 3 listeners updated and tested

### How to Run
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
python -m etl.main.run_all_listeners
```

---

## Run Commands

### All Listeners (Recommended)
```bash
python -m etl.main.run_all_listeners
```

### Individual Listeners
```bash
python -m etl.tpd.tpd_test_listener
python -m etl.tpd.tpd_truck_listener
python -m etl.tpd.tpd_scrapping_listener
```

### Test Connection
```bash
python test_kafka_connection.py
```

---

## What Changed

### From:
```python
value_deserializer=lambda m: json.loads(m.decode('utf-8'))
```

### To:
```python
def deserialize_message(message):
    # Handles JSON, plain text, binary, empty messages
    # Returns None/string/dict/bytes based on input
    # Logs all errors without crashing
    
value_deserializer=deserialize_message
```

---

## Message Handling

| Input | Output | Status |
|-------|--------|--------|
| `{"key": "value"}` | Python dict | ✅ Processed |
| `plain text` | String | ✅ Processed |
| Empty bytes | None | ⏭️ Skipped |
| Non-UTF8 binary | bytes | ✅ Processed |

---

## Expected Output

```
Starting listeners...
✓ Connected to localhost:9093
✓ Listening to 3 topics
✓ Received message: {"data": "test"}
✓ Processing message...
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Still getting JSON error | Restart listener after pulling latest code |
| No messages received | Send test messages via Kafka UI |
| Listener exited | Check logs for errors above |

---

## File Structure

```
etl/
├── main/
│   └── run_all_listeners.py     ← Run this
├── tpd/
│   ├── tpd_test_listener.py     ← Updated
│   ├── tpd_truck_listener.py    ← Updated  
│   └── tpd_scrapping_listener.py ← Updated
```

---

## Key Functions

```python
# In each listener file:

deserialize_message(message)
  ↓ Safely handles any message format
  
start_test_listener()
  ↓ Main listener loop
  
process_test_message(message)
  ↓ Add your custom logic here
```

---

## Add Custom Logic

Edit the `process_*_message` functions:

```python
def process_test_message(message):
    # Your business logic here
    if isinstance(message, dict):
        handle_json(message)
    else:
        handle_text(message)
```

---

## Topics & Groups

- **test-topic** → test-group
- **truck-topic** → truck-group  
- **scrapping-topic** → scrapping-group

All connect to: `localhost:9093`

---

## Documentation

- `COMPLETE_FIX_SUMMARY.md` - Full explanation
- `DESERIALIZATION_FIX.md` - Technical details
- `README.md` - General setup

---

✅ Ready to use!

