"""
External Data - Weather and Air Quality

Fetches weather and air quality data that impacts health and activity decisions.
Focused on actionable information for health conversations.
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import requests
import logging

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, User, ExternalContext
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherClient:
    """Client for fetching weather and air quality data"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize weather client

        Get free API key from: https://openweathermap.org/api
        """
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.weather_url = "http://api.openweathermap.org/data/2.5/weather"
        self.air_quality_url = "http://api.openweathermap.org/data/2.5/air_pollution"

    def get_weather_and_air_quality(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Get current weather and air quality for a location

        Args:
            location: City name

        Returns:
            Dict with weather and air quality data
        """
        if not self.api_key:
            logger.warning("No Weather API key found, using mock data")
            return self._get_mock_data(location)

        try:
            # Get weather data
            weather_data = self._fetch_weather(location)
            if not weather_data:
                return self._get_mock_data(location)

            # Get air quality data using coordinates from weather response
            lat = weather_data.get("coord", {}).get("lat")
            lon = weather_data.get("coord", {}).get("lon")

            air_quality_data = None
            if lat and lon:
                air_quality_data = self._fetch_air_quality(lat, lon)

            # Combine and format data
            return self._format_response(weather_data, air_quality_data)

        except Exception as e:
            logger.error(f"Error fetching real weather data for {location}: {e}", exc_info=True)
            return self._get_mock_data(location)

    def _fetch_weather(self, location: str) -> Optional[Dict]:
        """Fetch weather data from OpenWeatherMap"""
        try:
            params = {
                "q": location,
                "appid": self.api_key,
                "units": "metric"  # Celsius
            }

            response = requests.get(self.weather_url, params=params, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Weather API request failed for {location}: {e}", exc_info=True)
            return None

    def _fetch_air_quality(self, lat: float, lon: float) -> Optional[Dict]:
        """Fetch air quality data from OpenWeatherMap"""
        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key
            }

            response = requests.get(self.air_quality_url, params=params, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Air quality API request failed for {lat}, {lon}: {e}", exc_info=True)
            return None

    def _format_response(self, weather_data: Dict, air_quality_data: Optional[Dict]) -> Dict[str, Any]:
        """Format API responses into our standard format"""

        # Extract weather information
        temp = round(weather_data["main"]["temp"])
        condition = weather_data["weather"][0]["description"]
        humidity = weather_data["main"]["humidity"]

        # Extract air quality information
        air_quality = "unknown"
        aqi = None

        if air_quality_data and "list" in air_quality_data and air_quality_data["list"]:
            aqi = air_quality_data["list"][0]["main"]["aqi"]
            # Convert OpenWeather AQI (1-5) to descriptive text
            aqi_descriptions = {
                1: "good",
                2: "fair",
                3: "moderate",
                4: "poor",
                5: "very poor"
            }
            air_quality = aqi_descriptions.get(aqi, "unknown")
            # Convert to more standard 0-500 scale (approximate)
            aqi = (aqi - 1) * 100 + 25  # Rough conversion for display

        formatted_data = {
            "temperature": temp,
            "condition": condition,
            "humidity": humidity,
            "air_quality": air_quality,
            "air_quality_index": aqi
        }

        # Generate recommendations
        formatted_data["recommendations"] = self._get_activity_recommendations(formatted_data)

        logger.info(f"Successfully fetched real weather data: {temp}°C, {condition}, AQ: {air_quality}")

        return formatted_data

    def _get_mock_data(self, location: str) -> Dict[str, Any]:
        """Generate realistic mock weather and air quality data for POC"""

        # Mock data based on location
        mock_data = {
            "Tel Aviv": {
                "temperature": 24,
                "condition": "sunny",
                "humidity": 65,
                "air_quality_index": 45,
                "air_quality": "good"
            },
            "New York": {
                "temperature": 8,
                "condition": "cloudy",
                "humidity": 70,
                "air_quality_index": 85,
                "air_quality": "moderate"
            },
            "London": {
                "temperature": 12,
                "condition": "light rain",
                "humidity": 80,
                "air_quality_index": 55,
                "air_quality": "moderate"
            },
            "San Francisco": {
                "temperature": 18,
                "condition": "foggy",
                "humidity": 75,
                "air_quality_index": 35,
                "air_quality": "good"
            },
            "Toronto": {
                "temperature": 5,
                "condition": "snow",
                "humidity": 85,
                "air_quality_index": 40,
                "air_quality": "good"
            },
            "Sydney": {
                "temperature": 26,
                "condition": "partly cloudy",
                "humidity": 60,
                "air_quality_index": 50,
                "air_quality": "good"
            }
        }

        location_data = mock_data.get(location, {
            "temperature": 20,
            "condition": "clear",
            "humidity": 70,
            "air_quality_index": 50,
            "air_quality": "good"
        })

        result = {
            "temperature": location_data["temperature"],
            "condition": location_data["condition"],
            "humidity": location_data["humidity"],
            "air_quality_index": location_data["air_quality_index"],
            "air_quality": location_data["air_quality"],
            "recommendations": self._get_activity_recommendations(location_data)
        }

        logger.info(f"Using mock weather data for {location}: {result['temperature']}°C, {result['condition']}")
        return result

    def _get_activity_recommendations(self, weather_data: Dict[str, Any]) -> List[str]:
        """Generate activity recommendations based on weather and air quality"""

        recommendations = []
        temp = weather_data.get("temperature", 20)
        condition = weather_data.get("condition", "").lower()
        humidity = weather_data.get("humidity", 70)
        aqi = weather_data.get("air_quality_index", 50)

        # Temperature-based recommendations
        if temp < 0:
            recommendations.append("Very cold - indoor exercise recommended")
        elif temp < 10:
            recommendations.append("Cold weather - dress warmly for outdoor activities")
        elif temp > 32:
            recommendations.append("Very hot - exercise during cooler hours or indoors")
        elif temp > 28:
            recommendations.append("Hot weather - stay hydrated and avoid peak sun hours")
        elif 15 <= temp <= 25:
            recommendations.append("Great temperature for outdoor activities")

        # Weather condition recommendations
        if "rain" in condition or "storm" in condition:
            recommendations.append("Indoor exercise recommended due to rain")
        elif "snow" in condition:
            recommendations.append("Be cautious with outdoor activities due to snow")
        elif condition in ["sunny", "clear"]:
            recommendations.append("Perfect for outdoor exercise - don't forget sun protection")

        # Air quality recommendations
        if aqi and aqi > 150:
            recommendations.append("Poor air quality - avoid outdoor exercise")
        elif aqi and aqi > 100:
            recommendations.append("Moderate air quality - limit intense outdoor activities")
        elif aqi and aqi < 50:
            recommendations.append("Excellent air quality for outdoor activities")

        # Humidity recommendations
        if humidity > 85:
            recommendations.append("High humidity - take breaks during workouts")

        return recommendations[:2]  # Limit to 2 most relevant recommendations


class ExternalDataManager:
    """Simplified manager for weather and air quality data"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.weather_client = WeatherClient()

    def update_weather_data(self, locations: List[str]) -> Dict[str, bool]:
        """Update weather and air quality data for multiple locations"""

        results = {}
        session = self.db_manager.get_session()

        try:
            for location in locations:
                try:
                    weather_data = self.weather_client.get_weather_and_air_quality(location)

                    if weather_data:
                        # Store in database
                        external_context = ExternalContext(
                            context_type="weather",
                            location=location,
                            data=weather_data
                        )

                        session.add(external_context)
                        results[location] = True
                        logger.info(f"Updated weather data for {location}")
                    else:
                        results[location] = False
                        logger.warning(f"Failed to get weather data for {location}")

                except Exception as e:
                    logger.error(f"Error updating weather for {location}: {e}", exc_info=True)
                    results[location] = False

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Database error updating weather data: {e}", exc_info=True)
        finally:
            session.close()

        return results

    def get_user_external_context(self, user_location: str) -> Dict[str, Any]:
        """Get weather and air quality context for a user"""

        session = self.db_manager.get_session()

        try:
            # Get latest weather data for user's location
            weather_data = session.query(ExternalContext).filter(
                ExternalContext.context_type == "weather",
                ExternalContext.location == user_location
            ).order_by(ExternalContext.timestamp.desc()).first()

            if weather_data and weather_data.data:
                return {"weather": weather_data.data}
            else:
                # Fallback to mock data if no data in DB
                return {"weather": self.weather_client.get_weather_and_air_quality(user_location)}

        finally:
            session.close()

    def run_daily_update(self) -> Dict[str, Any]:
        """Run daily update of weather data for all user locations"""

        logger.info("Starting daily weather data update")

        # Get all unique user locations
        session = self.db_manager.get_session()
        try:
            locations = session.query(User.location).filter(
                User.location.isnot(None)
            ).distinct().all()

            location_list = [loc[0] for loc in locations if loc[0]]

        finally:
            session.close()

        # Update weather for all locations
        weather_results = self.update_weather_data(location_list)

        results = {
            "weather_updates": weather_results,
            "locations_processed": len(location_list),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Daily weather update complete: {results}")
        return results


# Convenience functions
def update_external_data() -> Dict[str, Any]:
    """Run external data update (convenience function)"""
    manager = ExternalDataManager()
    return manager.run_daily_update()


def get_user_context(user_location: str) -> Dict[str, Any]:
    """Get external context for a user (convenience function)"""
    manager = ExternalDataManager()
    return manager.get_user_external_context(user_location)


if __name__ == "__main__":
    # Test external data system
    print("=== TESTING EXTERNAL DATA SYSTEM ===")

    manager = ExternalDataManager()

    # Test daily update
    print("Running daily update...")
    results = manager.run_daily_update()
    print(f"Update results: {results}")

    # Test user context
    print("\nTesting user context for Tel Aviv...")
    context = manager.get_user_external_context("Tel Aviv")
    print(f"External context: {context}")