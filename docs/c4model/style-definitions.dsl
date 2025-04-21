    element "Person" {
        shape Person
        background #08427B
        color #ffffff
    }
    
    element "External System" {
        background #999999
        color #ffffff
    }
    
    element "Software System" {
        background #1168BD
        color #ffffff
    }
    
    element "Container" {
        background #438DD5
        color #ffffff
    }
    
    element "Microservice" {
        shape Hexagon
        background #FFD700
    }
    
    element "Database" {
        shape Cylinder
        background #F5F5F5
    }
    
    element "Message Bus" {
        shape Pipe
        background #FF8C00
    }
    
    element "Feature Store" {
        shape Cylinder
        background #85BBF0
        color #000000
    }

    element "Model Registry" {
        shape Cylinder
        background #6A5ACD
        color #ffffff
    }

    element "Elasticsearch" {
        shape Cylinder
        background #00BFB3
        color #000000
        icon "docs/icons/elasticsearch-icon.png"
    }
    
    element "Component" {
        background #85BBF0
    }
    
    element "Web Application" {
        shape WebBrowser
        background #D3D3D3
    }
    
    relationship "Relationship" {
        dashed false
        routing Direct
    }
    
    element "Python" {
        icon "docs/icons/python-icon.png"
    }
    
    element "Rust" {
        icon "docs/icons/rust-icon.png"
    }
    
    element "Kafka" {
        icon "docs/icons/kafka-icon.png"
    }
    
    element "Kubernetes" {
        icon "docs/icons/kubernetes-icon.png"
    }
    
    element "RisingWave" {
        icon "docs/icons/risingwave-icon.png"
    }
    
    element "MLflow" {
        icon "docs/icons/mlflow-icon.png"
    }
    
    element "Grafana" {
        icon "docs/icons/grafana-icon.png"
    }
