KAFKA LISTENERS - SETUP & USAGE GUIDE
=====================================

## Project Overview
This project contains Kafka listeners for three topics:
- test-topic (test-group)
- truck-topic (truck-group)
- scrapping-topic (scrapping-group)

All listeners are configured to connect to Kafka broker at localhost:9093

## Prerequisites
- Python 3.14+
- Kafka broker running on localhost:9093
- Kafka UI connection (which you've already verified is working)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

Current dependencies:
- kafka-python==2.3.2

## Files Structure

```
job-search/
├── tpd/
│   ├── __init__.py
│   ├── tpd_test_listener.py       # Listens to test-topic
│   ├── tpd_truck_listener.py      # Listens to truck-topic
│   └── tpd_scrapping_listener.py  # Listens to scrapping-topic
├── application.properties          # Configuration file with topic names
├── run_all_listeners.py           # Main runner - runs all 3 listeners in parallel
├── test_kafka_connection.py       # Diagnostic tool to test Kafka connection
└── requirements.txt               # Python dependencies
```

## Running the Application

### Option 1: Run All Listeners Together (RECOMMENDED)
```bash
python run_all_listeners.py
```
This starts all 3 listeners in parallel threads with synchronized logging.

### Option 2: Run Individual Listeners
```bash
python tpd/tpd_test_listener.py
python tpd/tpd_truck_listener.py
python tpd/tpd_scrapping_listener.py
```

### Option 3: Test Kafka Connection
Before running listeners, verify Kafka is accessible:
```bash
python test_kafka_connection.py
```

This will:
- Test connection to Kafka broker at localhost:9093
- List all available topics
- Verify required topics exist (test-topic, truck-topic, scrapping-topic)

## Expected Output

When running the listeners, you should see output like:
```
2026-06-06 15:54:00,000 - INFO - ================================================================================
2026-06-06 15:54:00,000 - INFO - ALL KAFKA LISTENERS RUNNER
2026-06-06 15:54:00,000 - INFO - ================================================================================
2026-06-06 15:54:00,000 - INFO - Running listeners for:
2026-06-06 15:54:00,000 - INFO -   1. test-topic (test-group)
2026-06-06 15:54:00,000 - INFO -   2. truck-topic (truck-group)
2026-06-06 15:54:00,000 - INFO -   3. scrapping-topic (scrapping-group)
2026-06-06 15:54:00,000 - INFO - ================================================================================
2026-06-06 15:54:00,000 - INFO - TestListenerThread - Starting all Kafka listeners...
2026-06-06 15:54:00,100 - INFO - TestListenerThread - Connecting to Kafka broker at localhost:9093...
2026-06-06 15:54:00,500 - INFO - TestListenerThread - Successfully connected to Kafka. Started test-topic listener
```

## Configuration Details

### Consumer Settings
Each listener uses:
- **bootstrap_servers**: localhost:9093
- **group_id**: {topic-name}-group (e.g., test-group, truck-group, scrapping-group)
- **auto_offset_reset**: earliest (starts from beginning if no offset found)
- **enable_auto_commit**: True (automatically commits processed messages)
- **session_timeout_ms**: 30000 (30 seconds)
- **request_timeout_ms**: 40000 (40 seconds)
- **connections_max_idle_ms**: 540000 (9 minutes)

### Customizing Message Processing
To add custom business logic, edit the process_* functions:
```python
def process_test_message(message):
    """Process incoming test message"""
    logger.info(f"Processing test message: {message}")
    # Add your business logic here
```

## Troubleshooting

### Issue: "Connection refused" or timeout errors
**Solution**: 
1. Verify Kafka is running on localhost:9093
2. Run `python test_kafka_connection.py` to diagnose
3. Check Kafka UI to confirm connection works

### Issue: "Topic not found" errors
**Solution**:
1. Create the topics in Kafka:
   ```bash
   # Using Kafka command line tools
   kafka-topics --create --topic test-topic --bootstrap-server localhost:9093
   kafka-topics --create --topic truck-topic --bootstrap-server localhost:9093
   kafka-topics --create --topic scrapping-topic --bootstrap-server localhost:9093
   ```
2. Or create via Kafka UI (which you've already verified works)

### Issue: Listeners receiving no messages
**Solution**:
1. Verify messages are being sent to the topics
2. Check consumer group offsets:
   ```bash
   kafka-consumer-groups --bootstrap-server localhost:9093 --list
   kafka-consumer-groups --bootstrap-server localhost:9093 --describe --group test-group
   ```
3. Reset group offset if needed:
   ```bash
   kafka-consumer-groups --bootstrap-server localhost:9093 --group test-group --reset-offsets --to-earliest --topic test-topic --execute
   ```

## Error Handling

The listeners include comprehensive error handling:
- Connection errors are logged with full stack traces
- Individual message processing errors don't crash the listener
- Consumer is properly closed on shutdown
- Proper null checks prevent NullPointerExceptions

## Log Levels

To change logging verbosity, edit the logging configuration in listener files:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Environment Variables (Optional)

For production, consider using environment variables:
```bash
export KAFKA_BOOTSTRAP_SERVERS="localhost:9093"
export KAFKA_SESSION_TIMEOUT="30000"
```

Then update listeners to use these values.

## Next Steps

1. Run the connection test:
   ```bash
   python test_kafka_connection.py
   ```

2. If all checks pass, run all listeners:
   ```bash
   python run_all_listeners.py
   ```

3. Send test messages to Kafka topics and watch them being processed

4. Customize the process_*_message() functions with your business logic

---

Happy Kafka processing! 🚀

