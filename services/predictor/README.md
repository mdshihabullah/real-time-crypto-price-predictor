# Crypto Price Predictor Service

This service analyzes technical indicators data from RisingWave and builds predictive models for cryptocurrency price movements.

## Features

- Fetches technical indicators data from RisingWave database
- Validates data quality using Great Expectations
- Profiles data with ydata-profiling
- Creates baseline models and advanced regression models
- Uses LazyPredict to identify best-performing model types
- Performs hyperparameter tuning with Optuna
- Tracks all experiments with MLflow
- Analyzes data drift and model drift with Evidently
- Generates comprehensive reports and artifacts

## Setup

1. Ensure you have Python 3.8+ installed
2. Install dependencies:

```bash
cd services/predictor
pip install -e .
```

3. Configure settings in `settings.env` (example provided)
4. Ensure RisingWave database is accessible
5. Ensure MLflow server is running at the configured URL (default: http://localhost:5001)

## Usage

Run the predictor with default settings (all pairs):

```bash
python -m src.run_predictor
```

Run for specific pairs:

```bash
python -m src.run_predictor --pairs BTC/EUR ETH/USD
```

### Command-line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--pairs` | Cryptocurrency pairs to process | All available pairs |
| `--prediction-horizon` | Prediction horizon in minutes | 5 |
| `--train-window` | Training window in days | 60 |
| `--validation-window` | Validation window in days | 14 |
| `--test-window` | Test window in days | 7 |
| `--max-trials` | Maximum number of hyperparameter optimization trials | 3 |
| `--top-models` | Number of top models to select from LazyPredict | 3 |
| `--log-file` | Path to log file | None (logs to stderr only) |
| `--generate-reports` | Generate data profiling and drift reports | False |

## Example

```bash
python -m src.run_predictor --pairs BTC/EUR --prediction-horizon 10 --max-trials 5 --generate-reports
```

## Outputs

- **Models**: Saved in MLflow model registry
- **Metrics**: Logged to MLflow tracking server
- **Profile Reports**: Generated in `reports/` directory
- **Drift Reports**: Generated in `drift_reports/` directory

## Architecture

The service follows a modular design with these key components:

- `data_fetcher.py`: Fetches data from RisingWave
- `data_validator.py`: Validates data quality
- `data_profiler.py`: Generates data profiles
- `data_preprocessor.py`: Prepares data for modeling
- `model_trainer.py`: Builds and tunes models
- `drift_analyzer.py`: Analyzes data and model drift
- `main.py`: Orchestrates the workflow
- `config.py`: Handles configuration settings

## Development

To contribute to this service:

1. Make changes to the relevant modules
2. Test your changes with a small dataset
3. Ensure all tests pass
4. Submit your changes for review
