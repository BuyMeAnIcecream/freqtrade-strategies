# Freqtrade Backtest GUI

A simple graphical user interface for running Freqtrade backtests without using the command line.

## Features

- **Strategy Selection**: Automatically detects and lists all available strategies from `user_data/strategies/`
- **Config File Selection**: Browse and select any JSON config file
- **Timeframe Selection**: Choose from common timeframes (1m, 5m, 15m, 30m, 1h, 4h, 1d)
- **Date Range**: Set custom start and end dates or use quick selection buttons
- **Output Management**: Choose where to save backtest results
- **Progress Tracking**: Visual progress bar and status updates
- **Error Handling**: Clear error messages and validation

## Requirements

- Python 3.6+
- tkinter (usually included with Python)
- Freqtrade installed and accessible via command line

## Installation

1. Make sure you have Freqtrade installed:
   ```bash
   pip install freqtrade
   ```

2. Place the GUI files in your Freqtrade strategies directory:
   - `backtest_gui.py`
   - `run_gui.py`

## Usage

### Quick Start

1. Run the launcher:
   ```bash
   python run_gui.py
   ```

2. Or run the GUI directly:
   ```bash
   python backtest_gui.py
   ```

### Using the GUI

1. **Select Strategy**: Choose from the dropdown list of available strategies
2. **Select Config File**: Browse and select your config file (defaults to `config_dip_testing.json`)
3. **Choose Timeframe**: Select your desired timeframe
4. **Set Date Range**: 
   - Enter dates manually in YYYYMMDD format, or
   - Use quick buttons: Last 7 Days, Last 30 Days, Last 90 Days, Last Year
5. **Select Output Folder**: Choose where to save the results
6. **Run Backtest**: Click "Run Backtest" and wait for completion

### Output

The GUI will:
- Show progress during the backtest
- Display success/error messages
- Save results to your chosen folder with timestamped filenames
- Show the command that was executed

## Example Usage

1. Select "DipBuyingStrategy" from the strategy dropdown
2. Choose "config_dip_testing.json" as the config file
3. Set timeframe to "15m"
4. Click "Last 30 Days" for quick date selection
5. Browse and select an output folder
6. Click "Run Backtest"

The GUI will execute:
```bash
freqtrade backtesting --config config_dip_testing.json --strategy DipBuyingStrategy --timerange 20240701-20240731 --timeframe 15m --export trades --export-filename /path/to/output/backtest_DipBuyingStrategy_20240803_162311.json
```

## Troubleshooting

### Common Issues

1. **"freqtrade not found"**: Make sure Freqtrade is installed and accessible in your PATH
2. **"No strategies found"**: Ensure you have strategy files in `user_data/strategies/`
3. **"Config file not found"**: Check that the config file path is correct
4. **"Invalid date format"**: Use YYYYMMDD format (e.g., 20240301 for March 1, 2024)

### Error Messages

The GUI provides detailed error messages for:
- Missing dependencies
- Invalid file paths
- Date format errors
- Freqtrade execution errors

## Customization

You can modify the GUI by editing `backtest_gui.py`:

- Add more timeframes to the `timeframe_combo` values
- Change default config file
- Modify the window size or layout
- Add additional validation rules

## File Structure

```
freqtrade-strategies/
├── backtest_gui.py          # Main GUI application
├── run_gui.py              # Launcher script
├── GUI_README.md           # This file
├── config_dip_testing.json # Example config
└── user_data/
    └── strategies/
        ├── DipBuyingStrategy.py
        └── ... (other strategies)
```

## Support

If you encounter issues:
1. Check that all requirements are met
2. Verify Freqtrade is working from command line
3. Check the error messages in the GUI
4. Ensure your config file is valid JSON 