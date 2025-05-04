""" Trade model """
from pydantic import BaseModel


class Trade(BaseModel):
    """
    Trade model
    """
    product_id: str
    price: float
    quantity: float
    timestamp: str
    timestamp_ms: int

    def to_dict(self) -> dict:
        """
        Convert the Trade model to a dictionary
        """
        return self.model_dump()
