# 3. Use Rust for Predictions API

Date: 2024-04-19

## Status

Accepted

## Context

Our system needs to serve predictions to external clients with:
1. Low latency responses
2. High throughput
3. Efficient resource utilization
4. Reliable operation under load
5. Security and stability

While most of our services are implemented in Python due to the rich ML ecosystem, we need to evaluate if Python is also the best choice for our user-facing API.

## Decision

We will implement the Predictions API service in Rust rather than Python for the following reasons:

1. Performance - Rust provides near-native performance with much lower latency
2. Resource efficiency - Rust has a smaller memory footprint than Python
3. Type safety - Rust's strong type system helps prevent runtime errors
4. Concurrency - Rust's ownership model enables safe concurrent programming
5. Security - Rust's memory safety guarantees reduce vulnerability risks

The rest of our microservices will continue to use Python where its data science ecosystem provides more value than raw performance.

## Consequences

### Positive

- Significantly improved API performance
- Lower infrastructure costs due to better resource utilization
- More reliable service under heavy load
- Enhanced security for our external-facing component
- Better handling of concurrent requests

### Negative

- Different language from the rest of the system increases complexity
- Smaller talent pool of Rust developers
- Steeper learning curve for team members unfamiliar with Rust
- Need for language interoperability when sharing code or libraries
- Potentially longer development time for new features 