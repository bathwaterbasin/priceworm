#!/usr/bin/env python3
"""
Biological Consensus Index - Market Correlation Framework
Correlates real-time biological/environmental data streams with market indices
to identify predictive biological signals for algorithmic trading
"""

import pandas as pd
import numpy as np
import requests
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from scipy.stats import pearsonr, spearmanr
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns

@dataclass
class DataStream:
    """Configuration for a biological/environmental data stream"""
    name: str
    api_endpoint: str
    api_key: str
    update_frequency: int  # minutes
    preprocessing_func: callable
    weight: float = 1.0

@dataclass
class CorrelationResult:
    """Results of correlation analysis between bio data and market index"""
    data_stream: str
    market_index: str
    correlation_coefficient: float
    p_value: float
    lag_minutes: int
    predictive_power: float
    confidence_level: float

class BiologicalConsensusIndex:
    """
    Main class for building and analyzing biological consensus index
    Correlates multiple biological data streams with market movements
    """
    
    def __init__(self):
        self.data_streams = {}
        self.market_apis = {}
        self.historical_data = {}
        self.correlations = {}
        self.consensus_weights = {}
        self.logger = self._setup_logging()
        
    def _setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    
    def add_data_stream(self, stream: DataStream):
        """Add a biological/environmental data stream"""
        self.data_streams[stream.name] = stream
        self.historical_data[stream.name] = pd.DataFrame()
        
    def add_market_index(self, name: str, api_endpoint: str, api_key: str):
        """Add a market index for correlation analysis"""
        self.market_apis[name] = {
            'endpoint': api_endpoint,
            'api_key': api_key
        }
        self.historical_data[f"market_{name}"] = pd.DataFrame()
    
    def setup_default_streams(self):
        """Setup commonly available biological/environmental data streams"""
        
        # Sensor.Community environmental sensors (12,000+ global sensors)
        self.add_data_stream(DataStream(
            name="sensor_community_temp",
            api_endpoint="https://data.sensor.community/airrohr/v1/filter/",
            api_key="",  # Public API
            update_frequency=5,
            preprocessing_func=self._process_sensor_community_temp
        ))
        
        # Meersens Environmental API (global environmental data)
        self.add_data_stream(DataStream(
            name="meersens_air_quality",
            api_endpoint="https://api.meersens.com/environment/public/air/current",
            api_key="YOUR_MEERSENS_API_KEY",
            update_frequency=5,
            preprocessing_func=self._process_meersens_data
        ))
        
        # Bioelectronic sensor simulation (electromagnetic sensitivity)
        self.add_data_stream(DataStream(
            name="electromagnetic_sensitivity",
            api_endpoint="custom_biosensor_endpoint",
            api_key="",
            update_frequency=2,
            preprocessing_func=self._process_electromagnetic_data
        ))
        
        # GBIF species occurrence changes (biological activity)
        self.add_data_stream(DataStream(
            name="species_activity",
            api_endpoint="https://api.gbif.org/v1/occurrence/search",
            api_key="",
            update_frequency=60,
            preprocessing_func=self._process_species_data
        ))
    
    def setup_default_markets(self):
        """Setup major market indices for correlation analysis"""
        
        # Alpha Vantage - Free tier available
        self.add_market_index(
            "SPY", 
            "https://www.alphavantage.co/query",
            "YOUR_ALPHA_VANTAGE_API_KEY"
        )
        
        # Polygon.io for real-time data
        self.add_market_index(
            "NASDAQ",
            "https://api.polygon.io/v2/aggs/ticker",
            "YOUR_POLYGON_API_KEY"
        )
        
        # Twelve Data for multiple indices
        self.add_market_index(
            "VIX",  # Volatility index
            "https://api.twelvedata.com/time_series",
            "YOUR_TWELVE_DATA_API_KEY"
        )
    
    async def fetch_data_stream(self, stream_name: str) -> Optional[Dict]:
        """Fetch data from a biological/environmental stream"""
        if stream_name not in self.data_streams:
            return None
            
        stream = self.data_streams[stream_name]
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {stream.api_key}"} if stream.api_key else {}
                
                async with session.get(stream.api_endpoint, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        processed_data = stream.preprocessing_func(data)
                        return processed_data
                    else:
                        self.logger.error(f"Failed to fetch {stream_name}: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error fetching {stream_name}: {e}")
            return None
    
    async def fetch_market_data(self, market_name: str) -> Optional[Dict]:
        """Fetch real-time market data"""
        if f"market_{market_name}" not in self.historical_data:
            return None
            
        api_config = self.market_apis[market_name]
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {api_config['api_key']}"}
                
                async with session.get(api_config['endpoint'], headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._process_market_data(data, market_name)
                    else:
                        self.logger.error(f"Failed to fetch {market_name}: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error fetching {market_name}: {e}")
            return None
    
    def _process_sensor_community_temp(self, data: Dict) -> Dict:
        """Process Sensor.Community temperature data"""
        try:
            temperatures = []
            humidity = []
            pressure = []
            
            for sensor in data:
                sensor_data = sensor.get('sensordatavalues', [])
                for reading in sensor_data:
                    if reading['value_type'] == 'temperature':
                        temperatures.append(float(reading['value']))
                    elif reading['value_type'] == 'humidity':
                        humidity.append(float(reading['value']))
                    elif reading['value_type'] == 'pressure':
                        pressure.append(float(reading['value']))
            
            return {
                'timestamp': datetime.utcnow(),
                'avg_temperature': np.mean(temperatures) if temperatures else None,
                'avg_humidity': np.mean(humidity) if humidity else None,
                'avg_pressure': np.mean(pressure) if pressure else None,
                'sensor_count': len(data)
            }
        except Exception as e:
            self.logger.error(f"Error processing sensor community data: {e}")
            return {}
    
    def _process_meersens_data(self, data: Dict) -> Dict:
        """Process Meersens environmental data"""
        try:
            return {
                'timestamp': datetime.utcnow(),
                'air_quality_index': data.get('indexes', {}).get('maqi', {}).get('value'),
                'pollution_level': data.get('indexes', {}).get('maqi', {}).get('qualification'),
                'temperature': data.get('weather', {}).get('temperature'),
                'humidity': data.get('weather', {}).get('humidity'),
                'pressure': data.get('weather', {}).get('pressure')
            }
        except Exception as e:
            self.logger.error(f"Error processing Meersens data: {e}")
            return {}
    
    def _process_electromagnetic_data(self, data: Dict) -> Dict:
        """Process bioelectronic electromagnetic sensitivity data"""
        # Simulated processing for electromagnetic sensor data
        try:
            return {
                'timestamp': datetime.utcnow(),
                'electromagnetic_field_strength': data.get('em_field', np.random.normal(50, 10)),
                'bacterial_response_current': data.get('bio_current', np.random.normal(2, 0.5)),
                'detection_threshold_exceeded': data.get('threshold_exceeded', False),
                'response_time_ms': data.get('response_time', np.random.uniform(1000, 3000))
            }
        except Exception as e:
            self.logger.error(f"Error processing electromagnetic data: {e}")
            return {}
    
    def _process_species_data(self, data: Dict) -> Dict:
        """Process GBIF species occurrence data"""
        try:
            recent_observations = data.get('results', [])
            return {
                'timestamp': datetime.utcnow(),
                'observation_count': len(recent_observations),
                'species_diversity': len(set(obs.get('speciesKey') for obs in recent_observations)),
                'geographic_spread': len(set(obs.get('countryCode') for obs in recent_observations)),
                'recent_activity_score': len([obs for obs in recent_observations 
                                            if self._is_recent_observation(obs)])
            }
        except Exception as e:
            self.logger.error(f"Error processing species data: {e}")
            return {}
    
    def _process_market_data(self, data: Dict, market_name: str) -> Dict:
        """Process market data from various APIs"""
        try:
            # Generic processing - adapt based on API response format
            return {
                'timestamp': datetime.utcnow(),
                'price': data.get('price', data.get('close', data.get('last'))),
                'volume': data.get('volume'),
                'change_percent': data.get('change_percent'),
                'volatility': data.get('volatility')
            }
        except Exception as e:
            self.logger.error(f"Error processing market data for {market_name}: {e}")
            return {}
    
    def _is_recent_observation(self, observation: Dict) -> bool:
        """Check if species observation is recent (within last 24 hours)"""
        try:
            obs_date = observation.get('eventDate')
            if obs_date:
                obs_datetime = datetime.fromisoformat(obs_date.replace('Z', '+00:00'))
                return (datetime.utcnow() - obs_datetime).total_seconds() < 86400
        except:
            pass
        return False
    
    async def collect_real_time_data(self):
        """Collect data from all configured streams and markets"""
        tasks = []
        
        # Collect biological/environmental data
        for stream_name in self.data_streams:
            tasks.append(self.fetch_data_stream(stream_name))
        
        # Collect market data
        for market_name in self.market_apis:
            tasks.append(self.fetch_market_data(market_name))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store results in historical data
        timestamp = datetime.utcnow()
        
        stream_results = results[:len(self.data_streams)]
        market_results = results[len(self.data_streams):]
        
        # Update historical data
        for i, (stream_name, result) in enumerate(zip(self.data_streams.keys(), stream_results)):
            if isinstance(result, dict) and result:
                new_row = pd.DataFrame([result])
                self.historical_data[stream_name] = pd.concat([
                    self.historical_data[stream_name], new_row
                ], ignore_index=True)
        
        for i, (market_name, result) in enumerate(zip(self.market_apis.keys(), market_results)):
            if isinstance(result, dict) and result:
                new_row = pd.DataFrame([result])
                self.historical_data[f"market_{market_name}"] = pd.concat([
                    self.historical_data[f"market_{market_name}"], new_row
                ], ignore_index=True)
    
    def calculate_correlations(self, lookback_hours: int = 24, 
                             max_lag_minutes: int = 60) -> List[CorrelationResult]:
        """
        Calculate correlations between biological data and market movements
        with various time lags to identify predictive relationships
        """
        correlations = []
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        for stream_name in self.data_streams:
            for market_name in self.market_apis:
                # Get recent data
                bio_data = self.historical_data[stream_name]
                market_data = self.historical_data[f"market_{market_name}"]
                
                if bio_data.empty or market_data.empty:
                    continue
                
                # Filter to recent data
                bio_data = bio_data[bio_data['timestamp'] >= cutoff_time]
                market_data = market_data[market_data['timestamp'] >= cutoff_time]
                
                if len(bio_data) < 10 or len(market_data) < 10:
                    continue
                
                # Test different lag periods
                for lag_minutes in range(0, max_lag_minutes + 1, 5):
                    correlation = self._calculate_lagged_correlation(
                        bio_data, market_data, stream_name, market_name, lag_minutes
                    )
                    
                    if correlation:
                        correlations.append(correlation)
        
        return sorted(correlations, key=lambda x: abs(x.correlation_coefficient), reverse=True)
    
    def _calculate_lagged_correlation(self, bio_data: pd.DataFrame, 
                                    market_data: pd.DataFrame,
                                    stream_name: str, market_name: str, 
                                    lag_minutes: int) -> Optional[CorrelationResult]:
        """Calculate correlation with time lag between bio and market data"""
        try:
            # Shift biological data by lag to test predictive power
            bio_shifted = bio_data.copy()
            bio_shifted['timestamp'] = bio_shifted['timestamp'] + timedelta(minutes=lag_minutes)
            
            # Merge on timestamp (within 1-minute tolerance)
            merged = pd.merge_asof(
                market_data.sort_values('timestamp'),
                bio_shifted.sort_values('timestamp'),
                on='timestamp',
                tolerance=pd.Timedelta('1min'),
                suffixes=('_market', '_bio')
            )
            
            if len(merged) < 10:
                return None
            
            # Extract numeric columns for correlation
            bio_numeric_cols = merged.select_dtypes(include=[np.number]).filter(regex='_bio').columns
            market_numeric_cols = merged.select_dtypes(include=[np.number]).filter(regex='_market').columns
            
            if not bio_numeric_cols.any() or not market_numeric_cols.any():
                return None
            
            # Calculate correlation for primary metrics
            bio_primary = merged[bio_numeric_cols[0]].dropna()
            market_primary = merged[market_numeric_cols[0]].dropna()
            
            if len(bio_primary) < 10 or len(market_primary) < 10:
                return None
            
            # Align the series
            min_len = min(len(bio_primary), len(market_primary))
            bio_primary = bio_primary.iloc[:min_len]
            market_primary = market_primary.iloc[:min_len]
            
            corr_coef, p_value = pearsonr(bio_primary, market_primary)
            
            # Calculate predictive power (simplified R-squared)
            predictive_power = corr_coef ** 2
            
            # Confidence level based on p-value
            confidence_level = 1 - p_value
            
            return CorrelationResult(
                data_stream=stream_name,
                market_index=market_name,
                correlation_coefficient=corr_coef,
                p_value=p_value,
                lag_minutes=lag_minutes,
                predictive_power=predictive_power,
                confidence_level=confidence_level
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating correlation: {e}")
            return None
    
    def calculate_consensus_index(self, correlations: List[CorrelationResult]) -> float:
        """
        Calculate the biological consensus index based on weighted correlations
        Higher values indicate biological factors suggest market optimism
        """
        if not correlations:
            return 0.0
        
        weighted_signals = []
        total_weight = 0
        
        for corr in correlations:
            if corr.confidence_level > 0.95:  # Only use high-confidence correlations
                # Get current biological signal
                current_bio_value = self._get_current_bio_signal(corr.data_stream)
                
                if current_bio_value is not None:
                    # Weight by predictive power and confidence
                    weight = corr.predictive_power * corr.confidence_level
                    
                    # Normalize signal based on correlation direction
                    normalized_signal = current_bio_value * np.sign(corr.correlation_coefficient)
                    
                    weighted_signals.append(normalized_signal * weight)
                    total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        consensus_index = sum(weighted_signals) / total_weight
        
        # Normalize to -1 to +1 range
        return np.tanh(consensus_index)
    
    def _get_current_bio_signal(self, stream_name: str) -> Optional[float]:
        """Get the most recent biological signal value"""
        if stream_name not in self.historical_data:
            return None
        
        data = self.historical_data[stream_name]
        if data.empty:
            return None
        
        # Get most recent numeric value
        latest_row = data.iloc[-1]
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        
        if not numeric_cols.any():
            return None
        
        return latest_row[numeric_cols[0]]
    
    def generate_trading_signal(self, consensus_index: float, 
                              threshold: float = 0.1) -> str:
        """
        Generate trading signal based on biological consensus index
        """
        if consensus_index > threshold:
            return "BUY"
        elif consensus_index < -threshold:
            return "SELL"
        else:
            return "HOLD"
    
    def plot_correlations(self, correlations: List[CorrelationResult], 
                         top_n: int = 20):
        """Plot the top correlations for visualization"""
        if not correlations:
            return
        
        top_correlations = correlations[:top_n]
        
        # Create correlation matrix plot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
        
        # Correlation coefficients
        stream_names = [c.data_stream for c in top_correlations]
        market_names = [c.market_index for c in top_correlations]
        corr_values = [c.correlation_coefficient for c in top_correlations]
        
        ax1.barh(range(len(corr_values)), corr_values)
        ax1.set_yticks(range(len(corr_values)))
        ax1.set_yticklabels([f"{s}->{m}" for s, m in zip(stream_names, market_names)])
        ax1.set_xlabel('Correlation Coefficient')
        ax1.set_title('Top Biological-Market Correlations')
        ax1.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        
        # Predictive power vs confidence
        predictive_powers = [c.predictive_power for c in top_correlations]
        confidence_levels = [c.confidence_level for c in top_correlations]
        
        scatter = ax2.scatter(confidence_levels, predictive_powers, 
                            c=corr_values, cmap='RdBu_r', alpha=0.6)
        ax2.set_xlabel('Confidence Level')
        ax2.set_ylabel('Predictive Power (R²)')
        ax2.set_title('Correlation Quality Matrix')
        plt.colorbar(scatter, ax=ax2, label='Correlation Coefficient')
        
        plt.tight_layout()
        plt.show()
    
    async def run_analysis_loop(self, collection_interval_minutes: int = 5,
                              analysis_interval_minutes: int = 15):
        """
        Main loop for continuous data collection and analysis
        """
        last_analysis = datetime.utcnow() - timedelta(minutes=analysis_interval_minutes)
        
        while True:
            try:
                # Collect real-time data
                await self.collect_real_time_data()
                self.logger.info("Data collection completed")
                
                # Perform correlation analysis periodically
                if (datetime.utcnow() - last_analysis).total_seconds() >= analysis_interval_minutes * 60:
                    correlations = self.calculate_correlations()
                    consensus_index = self.calculate_consensus_index(correlations)
                    trading_signal = self.generate_trading_signal(consensus_index)
                    
                    self.logger.info(f"Consensus Index: {consensus_index:.4f}")
                    self.logger.info(f"Trading Signal: {trading_signal}")
                    
                    # Log top correlations
                    if correlations:
                        top_corr = correlations[0]
                        self.logger.info(f"Top correlation: {top_corr.data_stream} -> "
                                       f"{top_corr.market_index} "
                                       f"(r={top_corr.correlation_coefficient:.3f}, "
                                       f"lag={top_corr.lag_minutes}min)")
                    
                    last_analysis = datetime.utcnow()
                
                # Wait before next collection
                await asyncio.sleep(collection_interval_minutes * 60)
                
            except Exception as e:
                self.logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

# Example usage
async def main():
    """Example of setting up and running the biological consensus index"""
    
    # Initialize the system
    bio_index = BiologicalConsensusIndex()
    
    # Setup data streams and markets
    bio_index.setup_default_streams()
    bio_index.setup_default_markets()
    
    # Run a single analysis cycle
    print("Collecting initial data...")
    await bio_index.collect_real_time_data()
    
    # Simulate some historical data for demonstration
    # In practice, you'd let this run for hours/days to collect real data
    print("Calculating correlations...")
    correlations = bio_index.calculate_correlations()
    
    if correlations:
        print(f"Found {len(correlations)} correlations")
        
        # Show top 5 correlations
        for i, corr in enumerate(correlations[:5]):
            print(f"{i+1}. {corr.data_stream} -> {corr.market_index}")
            print(f"   Correlation: {corr.correlation_coefficient:.3f}")
            print(f"   P-value: {corr.p_value:.3f}")
            print(f"   Lag: {corr.lag_minutes} minutes")
            print(f"   Predictive Power: {corr.predictive_power:.3f}")
            print()
        
        # Calculate consensus index
        consensus_index = bio_index.calculate_consensus_index(correlations)
        trading_signal = bio_index.generate_trading_signal(consensus_index)
        
        print(f"Biological Consensus Index: {consensus_index:.4f}")
        print(f"Trading Signal: {trading_signal}")
        
        # Plot results
        bio_index.plot_correlations(correlations)
    
    # Uncomment to run continuous analysis
    # await bio_index.run_analysis_loop()

if __name__ == "__main__":
    asyncio.run(main())
