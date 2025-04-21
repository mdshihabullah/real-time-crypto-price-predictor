# 2. Use RisingWave as Feature Store

Date: 2024-04-19

## Status

Accepted

## Context

Our machine learning pipeline requires a feature store to:
1. Store and serve features for model training and inference
2. Handle real-time feature updates from streaming data
3. Maintain feature consistency across training and inference
4. Scale with our growing data volume

We evaluated several options including traditional databases, specialized feature stores, and stream processing systems.

## Decision

We will use RisingWave as our feature store solution because:

1. It combines stream processing with materialized views, allowing us to both process and store features
2. It supports SQL for feature definition and access, reducing the learning curve
3. It handles both batch and streaming workloads efficiently
4. It scales horizontally with our data volume
5. It integrates well with Kafka, our messaging backbone
6. It has lower operational overhead compared to running separate stream processing and storage systems

## Consequences

### Positive

- Simplified architecture by combining stream processing and feature storage
- SQL interface for feature access is familiar to the team
- Real-time feature updates improve prediction freshness
- Horizontal scalability supports our growth projections
- Reduced operational complexity compared to separate systems

### Negative

- Relatively newer technology with smaller community
- Specialized knowledge required for optimization
- Limited third-party integrations compared to more established solutions
- May require custom development for advanced feature engineering patterns 