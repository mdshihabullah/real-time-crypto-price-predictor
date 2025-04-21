model {
    # People/Actors
    trader = person "Trader" "A user of the trading system who views predictions and market data"
    
    # External Systems
    newsAPI = softwareSystem "News API" "External service providing financial news" "External System"
    tradesAPI = softwareSystem "Trades API" "External service providing raw trade data from exchanges" "External System"
    
    # Main System
    cryptoSystem = softwareSystem "Crypto Price Prediction System" "Processes market data and predicts cryptocurrency prices" {
        # Data Ingestion & Processing
        sentimentExtractor = container "Sentiment Extractor" "Extracts sentiment from financial news" "Python, NLP" "Microservice" {
            textProcessor = component "Text Processor" "Preprocesses raw text"
            sentimentAnalyzer = component "Sentiment Analyzer" "Analyzes sentiment"
            entityRecognizer = component "Entity Recognizer" "Identifies cryptocurrencies"
            scorePublisher = component "Score Publisher" "Publishes sentiment scores"
        }
        
        llm = container "LLM" "Assists with sentiment analysis" "External LLM Service"
        
        tradeProcessor = container "Trade to OHLC" "Converts raw trade data to OHLC candles" "Python, Quixstreams" "Microservice" {
            tradeIngester = component "Trade Ingester" "Ingests raw trade data"
            candleAggregator = component "Candle Aggregator" "Aggregates trades into candles"
            publisher = component "Publisher" "Publishes candle data"
        }
        
        technicalIndicators = container "Technical Indicators" "Calculates technical indicators from OHLC data" "Python" "Microservice" {
            indicatorCalculator = component "Indicator Calculator" "Computes technical indicators"
            signalGenerator = component "Signal Generator" "Generates trading signals"
        }
        
        # Model Management
        modelTrainer = container "Model Trainer" "Trains prediction models using features" "Python, Scikit-learn" "Microservice" {
            dataCollector = component "Data Collector" "Fetches historical feature data"
            trainingPipeline = component "Training Pipeline" "Trains models with various algorithms"
            modelEvaluator = component "Model Evaluator" "Evaluates model performance"
            registryClient = component "Registry Client" "Registers models in MLflow"
        }
        
        modelRegistry = container "Model Registry" "Stores trained models and metadata" "MLflow" "Model Registry"
        
        # Prediction
        pricePredictor = container "Price Predictor" "Makes price predictions using trained models" "Python" "Microservice" {
            featureFetcher = component "Feature Fetcher" "Retrieves latest features"
            modelLoader = component "Model Loader" "Loads trained models"
            predictionEngine = component "Prediction Engine" "Generates predictions"
            predictionPublisher = component "Prediction Publisher" "Publishes predictions to Kafka"
        }
        
        predictionsAPI = container "Predictions API" "Exposes predictions to clients" "Rust" "Microservice"
        
        # Monitoring
        modelErrorMonitor = container "Model Error Monitor" "Monitors and reports prediction errors" "Python" "Microservice"
        
        # Data Storage
        featureStore = container "Feature Store" "Stores features for model training" "RisingWave" "Feature Store"
        elasticSearch = container "Elastic Search" "Stores predictions and model errors" "Elasticsearch" "Elasticsearch"
        
        # Messaging
        kafka = container "Message Broker" "Handles async messaging between services" "Kafka, Strimzi" "Message Bus"
        
        # Visualization
        dashboard = container "Dashboard" "Visualizes predictions and system metrics" "Grafana" "Web Application"
        alerts = container "Alerts" "Notifies users of significant events" "Alertmanager" "Web Application"
    }
    
    # External Relationships
    trader -> cryptoSystem "Uses to view predictions and analyses"
    trader -> dashboard "Views predictions and market data"
    trader -> alerts "Receives alerts on significant market events"
    trader -> predictionsAPI "Requests predictions via API"
    
    # Data Ingestion
    sentimentExtractor -> newsAPI "Fetches financial news from"
    sentimentExtractor -> llm "Uses for sentiment analysis"
    llm -> sentimentExtractor "Provides sentiment scores"
    tradeProcessor -> tradesAPI "Fetches trade data from"
    
    # Internal Relationships - Sentiment Flow
    sentimentExtractor -> kafka "Publishes sentiment data to"
    kafka -> featureStore "Streams sentiment data to"
    
    # Internal Relationships - Trade Data Flow
    tradeProcessor -> kafka "Publishes OHLC data to"
    kafka -> technicalIndicators "Streams OHLC data to"
    technicalIndicators -> kafka "Publishes technical indicators to"
    kafka -> featureStore "Streams technical indicators to"
    
    # Internal Relationships - Model Training
    featureStore -> modelTrainer "Provides features for model training"
    modelTrainer -> modelRegistry "Stores trained models in"
    
    # Internal Relationships - Prediction Flow
    featureStore -> pricePredictor "Provides features for prediction"
    modelRegistry -> pricePredictor "Provides trained models for prediction"
    pricePredictor -> kafka "Publishes predictions to"
    kafka -> elasticSearch "Streams predictions to"
    elasticSearch -> predictionsAPI "Provides predictions data to"
    pricePredictor -> elasticSearch "Stores predictions in"
    modelErrorMonitor -> elasticSearch "Stores error metrics in"

    # Internal Relationships - Monitoring
    kafka -> modelErrorMonitor "Streams prediction data to"
    modelErrorMonitor -> kafka "Publishes error metrics to"
    kafka -> elasticSearch "Streams error metrics to"
    
    # Internal Relationships - Visualization
    elasticSearch -> dashboard "Provides data for visualization"
    elasticSearch -> alerts "Provides data for alerting"
    
    # Component Relationships
    # Sentiment Extractor Components
    textProcessor -> sentimentAnalyzer "Passes processed text to"
    sentimentAnalyzer -> entityRecognizer "Passes analyzed text to"
    entityRecognizer -> scorePublisher "Passes entity-specific sentiment to"
    
    # Trade Processor Components
    tradeIngester -> candleAggregator "Passes trades to"
    candleAggregator -> publisher "Passes candles to"
    
    # Price Predictor Components
    featureFetcher -> predictionEngine "Provides features to"
    modelLoader -> predictionEngine "Provides models to"
    predictionEngine -> predictionPublisher "Passes predictions to"
    
    # Model Trainer Components
   dataCollector -> trainingPipeline "Provides datasets to"
   trainingPipeline -> modelEvaluator "Passes trained models to"
   modelEvaluator -> registryClient "Sends approved models to"
} 