KAFKA LISTENER - JSON DESERIALIZATION ERROR FIX
===============================================

## Problem
When running the listeners, they would crash with:
```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Root Cause
The original listeners used a simple lambda deserializer:
```python
value_deserializer=lambda m: json.loads(m.decode('utf-8'))
```

This would fail when:
1. ✗ Kafka messages were empty
2. ✗ Messages contained non-JSON data (plain text, binary, etc.)
3. ✗ Messages had encoding issues (not UTF-8)

The error occurred in Kafka's internal deserialization, before the message loop could catch it.

## Solution Applied

### 1. Created Robust Deserializer Function
Replaced the simple lambda with a comprehensive `deserialize_message()` function that:

```python
def deserialize_message(message):
    """
    Safe deserializer that handles JSON and raw data
    """
    if not message:
        logger.warning("Received empty message, skipping")
        return None
    
    try:
        # Step 1: Try to decode as UTF-8
        decoded = message.decode('utf-8')
        
        # Step 2: Try to parse as JSON
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            # Step 3: Fall back to raw string if not JSON
            logger.debug(f"Message is not JSON, returning as string: {decoded}")
            return decoded
            
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode as UTF-8: {str(e)}")
        return message  # Return raw bytes
    except Exception as e:
        logger.error(f"Error deserializing: {str(e)}", exc_info=True)
        return None
```

### 2. Updated All Three Listeners
- ✅ `/Users/nabeel.amd93/Desktop/Old-School/job-search/etl/tpd/tpd_test_listener.py`
- ✅ `/Users/nabeel.amd93/Desktop/Old-School/job-search/etl/tpd/tpd_truck_listener.py`
- ✅ `/Users/nabeel.amd93/Desktop/Old-School/job-search/etl/tpd/tpd_scrapping_listener.py`

### 3. Enhanced Message Loop
Added null check before processing:
```python
for message in consumer:
    try:
        if message.value is not None:  # ← NEW: Null check
            logger.info(f"Received message: {message.value}")
            process_test_message(message.value)
    except Exception as msg_err:
        logger.error(f"Error processing: {str(msg_err)}")
        continue
```

## Deserialization Flow

```
Kafka Message (bytes)
    ↓
[deserialize_message()]
    ├─→ Empty? → Return None (logged)
    ├─→ UTF-8 decode fails? → Return raw bytes (logged warning)
    ├─→ JSON parse succeeds? → Return parsed JSON object
    ├─→ JSON parse fails? → Return raw string (logged debug)
    └─→ Any other error? → Return None (logged error)
    ↓
Message Loop
    ├─→ if message.value is not None
    ├─→ logger.info(f"Received: {message.value}")
    ├─→ process_*_message(message.value)
    └─→ Exception? → Log & continue
```

## What This Handles

✅ **Empty messages** - Skipped with warning
✅ **JSON messages** - Parsed into Python objects
✅ **Plain text messages** - Returned as strings
✅ **Binary data** - Returned as bytes
✅ **Encoding issues** - Handled gracefully
✅ **Processing errors** - Caught and logged, doesn't crash listener

## Benefits

1. **Robustness** - Listener won't crash on malformed messages
2. **Flexibility** - Accepts JSON, plain text, or binary data
3. **Debuggability** - Clear logging of what went wrong
4. **Resilience** - Continues processing on errors
5. **Type Safety** - Null checks prevent NullPointerExceptions

## How to Use

### Run All Listeners:
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
python -m etl.main.run_all_listeners
```

### Run Individual Listeners:
```bash
python -m etl.tpd.tpd_test_listener
python -m etl.tpd.tpd_truck_listener
python -m etl.tpd.tpd_scrapping_listener
```

## Expected Output

```
2026-06-06 15:59:09,652 - __main__ - INFO - Connecting to Kafka broker at localhost:9093...
2026-06-06 15:59:09,652 - __main__ - INFO - Successfully connected to Kafka. Started test-topic listener
2026-06-06 15:59:13,093 - __main__ - INFO - Received message from test-topic: {"key": "value"}
2026-06-06 15:59:13,093 - __main__ - INFO - Processing test message: {"key": "value"}
2026-06-06 15:59:14,100 - __main__ - INFO - Received message from test-topic: plain text
2026-06-06 15:59:14,100 - __main__ - INFO - Processing test message: plain text
```

## Logging Levels

**WARNING**: Empty or encoding errors
**DEBUG**: Non-JSON messages being returned as strings
**ERROR**: Critical deserialization failures

Control debug output by setting log level:
```python
# In listener files, change line 10:
logging.basicConfig(
    level=logging.DEBUG,  # or INFO, WARNING, ERROR
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Files Updated

1. `etl/tpd/tpd_test_listener.py` - Added deserialize_message()
2. `etl/tpd/tpd_truck_listener.py` - Added deserialize_message()
3. `etl/tpd/tpd_scrapping_listener.py` - Added deserialize_message()

## Testing

To test the new deserializer with different message types:

1. Send valid JSON:
   ```
   {"timestamp": 1234567890, "data": "test"}
   ```

2. Send plain text:
   ```
   This is plain text
   ```

3. Send empty message (topic will skip with warning)

4. All should be processed without crashing!

## Troubleshooting

### Still getting JSON errors?
- Check Kafka is sending valid UTF-8 encoded messages
- Check message encoding in Kafka UI
- Verify Kafka version compatibility: `kafka-python==2.3.2`

### Listener still crashes?
- Check logs for specific error message
- May be a different error, not deserialization
- Run individual listener to isolate issue

### Not receiving any messages?
- Verify messages exist in Kafka topics
- Check consumer group offsets
- Try resetting group offset to earliest:
  ```bash
  kafka-consumer-groups --bootstrap-server localhost:9093 \
    --group test-group --reset-offsets --to-earliest \
    --topic test-topic --execute
  ```

## Summary

✅ **Issue Fixed**: JSON deserialization errors eliminated
✅ **Robustness**: Handles any message format gracefully
✅ **Flexibility**: Works with JSON, text, and binary data
✅ **Ready to Use**: All listeners updated and tested

🚀 Ready for production use!

