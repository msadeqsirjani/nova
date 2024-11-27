import requests
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import json
from pathlib import Path
from dataclasses import dataclass
from src.config import Config

@dataclass
class WeatherData:
    temperature: float
    feels_like: float
    humidity: int
    description: str
    wind_speed: float
    location: str
    timestamp: datetime
    condition: str
    icon: str

class WeatherService:
    def __init__(self, config: Config):
        """
        Initialize the weather service.
        
        Args:
            config (Config): Application configuration object
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Get API key from config
        self.api_key = config.get('api_keys', 'openweather_api_key')
        if not self.api_key:
            self.logger.error("OpenWeather API key not found in configuration")
            raise ValueError("OpenWeather API key is required")
        
        # API endpoints
        self.base_url = "http://api.openweathermap.org/data/2.5"
        self.geocoding_url = "http://api.openweathermap.org/geo/1.0"
        
        # Cache settings
        self.cache_dir = Path("cache/weather")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = 1800  # 30 minutes in seconds
    
    def _setup_logging(self):
        """Configure logging for the weather service"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get_current_weather(self, 
                          location: str, 
                          use_cache: bool = True) -> Optional[WeatherData]:
        """
        Get current weather for a location.
        
        Args:
            location (str): City name or "latitude,longitude"
            use_cache (bool): Whether to use cached data if available
            
        Returns:
            Optional[WeatherData]: Weather data if successful, None otherwise
        """
        try:
            # Check cache first
            if use_cache:
                cached_data = self._get_cached_weather(location)
                if cached_data:
                    self.logger.info(f"Using cached weather data for {location}")
                    return cached_data
            
            # Get coordinates if location is a city name
            if ',' not in location:
                coordinates = self._get_coordinates(location)
                if not coordinates:
                    raise ValueError(f"Could not find coordinates for {location}")
                lat, lon = coordinates
            else:
                lat, lon = map(float, location.split(','))
            
            # Make API request
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'  # Use metric units
            }
            
            response = requests.get(
                f"{self.base_url}/weather",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Parse response into WeatherData
            weather_data = WeatherData(
                temperature=data['main']['temp'],
                feels_like=data['main']['feels_like'],
                humidity=data['main']['humidity'],
                description=data['weather'][0]['description'],
                wind_speed=data['wind']['speed'],
                location=data['name'],
                timestamp=datetime.now(),
                condition=data['weather'][0]['main'],
                icon=data['weather'][0]['icon']
            )
            
            # Cache the results
            self._cache_weather(location, weather_data)
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Error getting weather data: {str(e)}")
            return None
    
    def get_forecast(self, 
                    location: str, 
                    days: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get weather forecast for a location.
        
        Args:
            location (str): City name or "latitude,longitude"
            days (int): Number of days to forecast (max 7)
            
        Returns:
            Optional[Dict[str, Any]]: Forecast data if successful, None otherwise
        """
        try:
            # Limit days to 7
            days = min(days, 7)
            
            # Get coordinates if needed
            if ',' not in location:
                coordinates = self._get_coordinates(location)
                if not coordinates:
                    raise ValueError(f"Could not find coordinates for {location}")
                lat, lon = coordinates
            else:
                lat, lon = map(float, location.split(','))
            
            # Make API request
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day
            }
            
            response = requests.get(
                f"{self.base_url}/forecast",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            return self._parse_forecast(response.json())
            
        except Exception as e:
            self.logger.error(f"Error getting forecast data: {str(e)}")
            return None
    
    def _get_coordinates(self, city: str) -> Optional[tuple]:
        """Get coordinates for a city name"""
        try:
            params = {
                'q': city,
                'limit': 1,
                'appid': self.api_key
            }
            
            response = requests.get(
                f"{self.geocoding_url}/direct",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if data:
                return data[0]['lat'], data[0]['lon']
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting coordinates: {str(e)}")
            return None
    
    def _get_cached_weather(self, location: str) -> Optional[WeatherData]:
        """Get weather data from cache if available and fresh"""
        try:
            cache_file = self.cache_dir / f"{location.replace(',', '_')}.json"
            if cache_file.exists():
                data = json.loads(cache_file.read_text())
                cached_time = datetime.fromisoformat(data['timestamp'])
                
                # Check if cache is still valid
                if (datetime.now() - cached_time).total_seconds() < self.cache_duration:
                    return WeatherData(
                        temperature=data['temperature'],
                        feels_like=data['feels_like'],
                        humidity=data['humidity'],
                        description=data['description'],
                        wind_speed=data['wind_speed'],
                        location=data['location'],
                        timestamp=cached_time,
                        condition=data['condition'],
                        icon=data['icon']
                    )
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading cache: {str(e)}")
            return None
    
    def _cache_weather(self, location: str, weather: WeatherData):
        """Cache weather data"""
        try:
            cache_file = self.cache_dir / f"{location.replace(',', '_')}.json"
            
            data = {
                'temperature': weather.temperature,
                'feels_like': weather.feels_like,
                'humidity': weather.humidity,
                'description': weather.description,
                'wind_speed': weather.wind_speed,
                'location': weather.location,
                'timestamp': weather.timestamp.isoformat(),
                'condition': weather.condition,
                'icon': weather.icon
            }
            
            cache_file.write_text(json.dumps(data, indent=2))
            
        except Exception as e:
            self.logger.error(f"Error writing cache: {str(e)}")
    
    def _parse_forecast(self, data: Dict) -> Dict[str, Any]:
        """Parse forecast API response into a more usable format"""
        forecast = {
            'location': data['city']['name'],
            'country': data['city']['country'],
            'forecasts': []
        }
        
        current_date = None
        daily_data = None
        
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            
            # Start new day
            if current_date != dt.date():
                if daily_data:
                    forecast['forecasts'].append(daily_data)
                current_date = dt.date()
                daily_data = {
                    'date': current_date.isoformat(),
                    'temp_min': float('inf'),
                    'temp_max': float('-inf'),
                    'conditions': set(),
                    'hourly': []
                }
            
            # Update daily summary
            daily_data['temp_min'] = min(daily_data['temp_min'], item['main']['temp_min'])
            daily_data['temp_max'] = max(daily_data['temp_max'], item['main']['temp_max'])
            daily_data['conditions'].add(item['weather'][0]['main'])
            
            # Add hourly data
            daily_data['hourly'].append({
                'time': dt.strftime('%H:%M'),
                'temp': item['main']['temp'],
                'feels_like': item['main']['feels_like'],
                'humidity': item['main']['humidity'],
                'condition': item['weather'][0]['main'],
                'description': item['weather'][0]['description'],
                'wind_speed': item['wind']['speed']
            })
        
        # Add last day
        if daily_data:
            forecast['forecasts'].append(daily_data)
            
        # Convert condition sets to lists
        for day in forecast['forecasts']:
            day['conditions'] = list(day['conditions'])
        
        return forecast
