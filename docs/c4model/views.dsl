views {

        
    styles {
        !include style-definitions.dsl
    }
    # System Context View
    systemContext cryptoSystem "SystemContext" {
        include *
        autoLayout lr
        description "The system context diagram for the Crypto Price Prediction System"
    }
    
    # Container View
    container cryptoSystem "Containers" {
        include *
        autoLayout lr
        description "The container diagram for the Crypto Price Prediction System"
    }
    
    # Component Views (C3 level)
    component sentimentExtractor "SentimentExtractorComponents" {
        include *
        autoLayout tb
        description "Components of the Sentiment Extractor service"
    }
    
    component tradeProcessor "TradeProcessorComponents" {
        include *
        autoLayout tb
        description "Components of the Trade Processor service"
    }
    
    component technicalIndicators "TechnicalIndicatorsComponents" {
        include *
        autoLayout tb
        description "Components of the Technical Indicators service"
    }
    
    component pricePredictor "PricePredictorComponents" {
        include *
        autoLayout tb
        description "Components of the Price Predictor service"
    }
    
    component modelTrainer "ModelTrainerComponents" {
        include *
        autoLayout tb
        description "Components of the Model Trainer service"
    }
    
    # Data Flow Views
    dynamic cryptoSystem "RawDataToFeatures" {
        title "From Raw Data to ML Features"
        autoLayout
        tradesAPI -> tradeProcessor "Provides trade data"
        tradeProcessor -> kafka "Publishes OHLC data"
        kafka -> technicalIndicators "Streams OHLC data"
        technicalIndicators -> kafka "Publishes indicators"
        kafka -> featureStore "Stores technical indicators"
        newsAPI -> sentimentExtractor "Provides financial news"
        llm -> sentimentExtractor "Provides sentiment analysis"
        sentimentExtractor -> kafka "Publishes sentiment data"
        kafka -> featureStore "Stores sentiment features"
        description "Shows how raw data is transformed into ML features"
    }
    
    dynamic cryptoSystem "ModelTrainingFlow" {
        title "From Historical Data to Model Artifact"
        autoLayout
        featureStore -> modelTrainer "Provides historical features"
        modelTrainer -> modelRegistry "Registers trained models"
        description "Shows the model training pipeline"
    }
    
    dynamic cryptoSystem "InferencePipeline" {
        title "Generate Predictions"
        autoLayout
        featureStore -> pricePredictor "Provides features"
        modelRegistry -> pricePredictor "Provides trained models"
        pricePredictor -> elasticSearch "Stores predictions"
        elasticSearch -> predictionsAPI "Serves predictions"
        description "Shows how predictions are generated and served"
    }
    
    dynamic cryptoSystem "ErrorMonitoring" {
        title "Prediction Error Monitoring Pipeline"
        autoLayout
        elasticSearch -> modelErrorMonitor "Provides prediction data"
        modelErrorMonitor -> elasticSearch "Stores error metrics"
        elasticSearch -> dashboard "Visualizes errors"
        elasticSearch -> alerts "Triggers alerts"
        description "Shows how prediction errors are monitored"
    }
    
    # container Views for Pipeline Focus
    container cryptoSystem "TechnicalIndicatorsPipeline" "Shows the technical indicators data pipeline" {
        include tradesAPI tradeProcessor kafka technicalIndicators featureStore
        autoLayout
    }

    container cryptoSystem "MarketSentimentPipeline" "Shows the market sentiment data pipeline" {
        include newsAPI sentimentExtractor llm kafka featureStore
        autoLayout
    }

    container cryptoSystem "MLPlatformView" "Shows the ML platform components" {
        include featureStore modelRegistry elasticSearch
        autoLayout
    }

    
    # TODO: Deployment View ( For later)


} 