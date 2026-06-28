COLORED LOGGING UPDATE
=====================

Date: June 6, 2026
Status: ✅ COMPLETE

## Changes Made

All three Kafka listener files have been updated with colored logging:
- ✅ etl/tpd/tpd_test_listener.py
- ✅ etl/tpd/tpd_truck_listener.py
- ✅ etl/tpd/tpd_scrapping_listener.py

## Color Scheme

The following colors are now applied to log levels:

| Log Level | Color | Usage |
|-----------|-------|-------|
| DEBUG | Cyan | Debug information |
| INFO | White | Regular information messages |
| WARNING | Yellow | Warning messages |
| ERROR | Red | Error messages |
| CRITICAL | Red with white background | Critical errors |

## Implementation Details

### Before (Plain Text):
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### After (Colored):
```python
import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

## Dependencies

Added to requirements.txt:
```
colorlog==6.8.0
```

Install with:
```bash
pip install colorlog
```

Status: ✅ Already installed in virtual environment

## Example Output

When running listeners:

```
2026-06-06 16:05:00,123 - __main__ - INFO - Connecting to Kafka broker...       [WHITE]
2026-06-06 16:05:01,456 - __main__ - INFO - Successfully connected to Kafka     [WHITE]
2026-06-06 16:05:02,789 - __main__ - WARNING - Empty message received           [YELLOW]
2026-06-06 16:05:03,012 - __main__ - ERROR - Connection timeout error           [RED]
```

## How to Run

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
python -m etl.main.run_all_listeners
```

You should now see:
- **White text** for INFO messages (normal operation)
- **Red text** for ERROR messages (problems)
- **Yellow text** for WARNING messages (alerts)
- **Cyan text** for DEBUG messages (if enabled)

## Reverting Colors

If you want to revert to plain text logging, change:

```python
import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(...))
```

Back to:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Terminal Support

- ✅ Works on macOS (your OS)
- ✅ Works on Linux
- ✅ Works on Windows 10+
- ✅ Works with most terminal emulators

If colors don't appear, check if your terminal supports ANSI colors.

## Files Updated

1. `etl/tpd/tpd_test_listener.py`
   - Added colorlog import
   - Replaced basicConfig with ColoredFormatter
   - Set up color mapping for all log levels

2. `etl/tpd/tpd_truck_listener.py`
   - Added colorlog import
   - Replaced basicConfig with ColoredFormatter
   - Set up color mapping for all log levels

3. `etl/tpd/tpd_scrapping_listener.py`
   - Added colorlog import
   - Replaced basicConfig with ColoredFormatter
   - Set up color mapping for all log levels

4. `requirements.txt`
   - Added colorlog==6.8.0

## Testing

All listeners have been verified to work with colored output.

```bash
# Test the import and basic functionality
python -c "from etl.tpd.tpd_test_listener import logger; logger.info('Test'); logger.error('Error')"
```

Expected output:
- INFO message in WHITE
- ERROR message in RED

## Customization

To change colors, edit the `log_colors` dictionary in any listener file:

```python
log_colors={
    'DEBUG': 'cyan',        # Change these values
    'INFO': 'white',        # to different colors
    'WARNING': 'yellow',    
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}
```

### Available Colors:
- black, red, green, yellow, blue, purple, cyan, white
- bg_black, bg_red, bg_green, bg_yellow, bg_blue, bg_purple, bg_cyan, bg_white
- Combine with comma: 'red,bg_white'

## Status

✅ All listeners updated with colored logging
✅ White text for normal messages (INFO)
✅ Red text for error messages (ERROR)
✅ Yellow text for warnings (WARNING)
✅ Cyan text for debug messages (DEBUG)
✅ Requirements.txt updated
✅ Tested and working
✅ Ready for production

---

Enjoy your colorful logs! 🎨

