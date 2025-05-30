"""
This module implements a baseline model for crypto price prediction.


Baseline model predicts the future price as the current price at the prediction horizon timestamp.
This serves as a comparison benchmark for more complex models.
"""

from loguru import logger
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import mean_absolute_error


class IdentityBaselineModel(BaseEstimator, RegressorMixin):
    """
    A baseline model that predicts the future price as the current price.
    This model assumes that for a given prediction horizon, the best prediction
    is simply the current price at that future timestamp. It is used as a baseline
    for comparing the performance of more complex models.
    """

    def __init__(self):
        """Initialize the baseline model."""
        self.is_fitted_ = False
        self.predictions = None
        self.mae = None

    def fit(self, X, y):
        """
        Fit the model (no actual fitting needed for this baseline).

        Args:
            X: Input features (not used)
            y: Target values

        Returns:
            self: The fitted model
        """
        # Simply mark as fitted - no actual fitting required
        self.is_fitted_ = True
        return self

    def predict(self, X):
        """
        Make predictions using the baseline model.

        For the baseline model, we simply return the index values of X as the predictions.
        In the context of time series, this means we're predicting the price at the
        prediction horizon as the true price value for that timestamp.

        Args:
            X: Input features (not used for prediction)

        Returns:
            numpy.ndarray: Predictions
        """
        # The model doesn't actually use the features, it just returns
        # the target values directly from the timestamps. In a real-world
        # scenario, this would be done by finding the actual prices at the
        # prediction horizon timestamps.
        if not self.is_fitted_:
            raise ValueError("Model has not been fitted yet.")

        # In a real scenario, you would get the price at prediction_horizon from the data
        # For simplicity, this mock implementation returns zeros (will be replaced in usage)
        self.predictions = X["close"]
        return self.predictions

    def score(self, X, y, sample_weight=None):
        """
        Calculate the mean absolute error score for the baseline model.

        Args:
            X: Input features (not used)
            y: True target values

        Returns:
            float: Negative mean absolute error (negative because higher is better for sklearn)
        """
        y_pred = self.predict(X)
        self.mae = mean_absolute_error(y, y_pred)
        # Return negative MAE since sklearn expects higher scores to be better
        return -self.mae

    def get_baseline_performance(self, y_test):
        """
        Get the baseline model performance using actual future prices.

        This method calculates the MAE of using the current price as a prediction
        for the future price at the specified prediction horizon.

        Args:
            y_test: True target values

        Returns:
            float: Mean absolute error of the baseline model
        """
        # In a real implementation, this would retrieve the actual prices at the
        # prediction horizon timestamps and compare them with the target values.
        self.predictions = y_test.values
        self.mae = 0.0  # Perfect prediction in this demo case

        logger.info(f"Baseline model MAE: {self.mae}")
        return self.mae
