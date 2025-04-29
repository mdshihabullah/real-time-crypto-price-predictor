### Overview

Introducing the intial setup and structure for the software architecture documentation of "Real time Crypto-currency Price Prediction System" using the C4 model implemented with Structurizr. It provides a hierarchical set of diagrams that document our system at multiple levels of abstraction, making it easier for all stakeholders to understand the architecture.

The implementation aligns with a larger initiative to improve technical documentation and supports our architectural governance process. It also ease and simplify future extensions of the architecture based on C4 Model concept as it evolves.

### What's Included

**Context Diagram:** Shows the system in its environment with external users and systems based on generic assumption
**Container Diagrams:** Initial Illustration the high-level technology decisions and how our system components communicate
**Component Diagrams:** Details for one or two  internal components and their relationships
**Architecture Decision Records (ADRs):** Sample documents key technology choices including MLFlow, Grafana, and Quix Streams etc

### Benefits

**Improved Onboarding:** New team members can quickly understand the system architecture
**Better Communication:** Consistent terminology and visualization across technical and non-technical stakeholders
**Enhanced Decision Making:** Clearer understanding of system boundaries and component interactions
**Living Documentation:** Structured in code to evolve with the system rather than becoming outdated

### Implementation Notes

The diagrams tries adhering the standard C4 model notation for consistency

Structurizr is used to define the model as code, ensuring documentation stays in sync with implementation
All diagrams use a consistent styling and naming convention for readability

### Testing/Viewing in Development Environment:

- To build the C4 Model, run the following command in the root directory:

    `docker build -t structurizr:dev -f docker/structurizr.Dockerfile .`


- To load and launch the deployment it in the local kind cluster named `rwml-34fa` :
    ```
            kind load docker-image structurizr:dev --name rwml-34fa
            kubectl apply -f deployments/dev/structurizr/structurizr.yaml
        # These operations need the namespace specified
        kubectl rollout restart deployment/structurizr-lite -n c4model
        kubectl wait --for=condition=ready pod -l app=structurizr-lite -n c4model --timeout=60s
    ```

Then using k9s or kubectl, you can port-forward the structurizr 8080 port to your desired local port to access the documentation via browser.