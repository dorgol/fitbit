"""
Mock Data Generator - Creates realistic health data for testing

Generates sample users, health metrics, and basic conversation history.
DOES NOT generate insights or highlights - those are created by their respective processors.
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from typing import List
import uuid

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, User, HealthMetric, Conversation,
    ExternalContext, KnowledgeBase
)


class MockDataGenerator:
    """Generates realistic mock data for testing - RAW DATA ONLY"""

    def __init__(self):
        self.db_manager = DatabaseManager()

        # Sample data patterns
        self.sample_names = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry"]
        self.sample_locations = ["Tel Aviv", "New York", "London", "San Francisco", "Toronto", "Sydney"]
        self.sample_goals = [
            ["lose_weight", "10k_steps_daily"],
            ["better_sleep", "reduce_stress"],
            ["marathon_training", "improve_endurance"],
            ["general_fitness", "consistent_exercise"],
            ["heart_health", "lower_resting_hr"],
            ["better_sleep", "morning_workouts"]
        ]

    def generate_sample_users(self, count: int = 5) -> List[int]:
        """Generate sample users with varied profiles"""
        user_ids = []
        session = self.db_manager.get_session()

        try:
            for i in range(count):
                user = User(
                    age=random.randint(22, 65),
                    gender=random.choice(["M", "F", "Other"]),
                    location=random.choice(self.sample_locations),
                    goals=random.choice(self.sample_goals),
                    preferences={
                        "communication_style": random.choice(["encouraging", "analytical", "casual"]),
                        "data_detail_level": random.choice(["high", "medium", "low"]),
                        "notification_frequency": random.choice(["daily", "weekly", "as_needed"]),
                        "preferred_exercise": random.choice(["walking", "running", "cycling", "gym", "yoga"])
                    }
                )
                session.add(user)
                session.flush()  # This assigns the ID without committing
                user_ids.append(user.id)  # Get the ID while session is active

            session.commit()
            print(f"✓ Created {count} sample users")

        except Exception as e:
            session.rollback()
            print(f"✗ Error creating users: {e}")
        finally:
            session.close()

        return user_ids

    def generate_health_metrics(self, user_id: int, days_back: int = 30):
        """Generate realistic health metrics for a user over time - RAW DATA ONLY"""
        session = self.db_manager.get_session()

        try:
            # Base patterns for this user (individual variation)
            base_steps = random.randint(6000, 12000)
            base_resting_hr = random.randint(55, 75)
            base_sleep_hours = random.uniform(6.5, 8.5)

            for day in range(days_back):
                # Calculate date
                date = datetime.now(timezone.utc) - timedelta(days=day)

                # Day of week patterns
                is_weekend = date.weekday() >= 5

                # Generate daily steps (lower on weekends, some variation)
                daily_steps = base_steps
                if is_weekend:
                    daily_steps = int(daily_steps * random.uniform(0.7, 1.2))
                else:
                    daily_steps = int(daily_steps * random.uniform(0.8, 1.3))

                # Add daily step entry
                session.add(HealthMetric(
                    user_id=user_id,
                    metric_type="steps",
                    value=daily_steps,
                    timestamp=date.replace(hour=23, minute=59),
                    extra_data={"day_of_week": date.strftime("%A")}
                ))

                # Generate heart rate readings (3 per day: morning, afternoon, evening)
                for hour in [8, 14, 20]:
                    # Resting HR varies slightly
                    hr_variation = random.uniform(-5, 5)
                    # Higher HR in afternoon
                    if hour == 14:
                        hr_variation += random.uniform(5, 15)

                    hr_value = max(50, base_resting_hr + hr_variation)

                    session.add(HealthMetric(
                        user_id=user_id,
                        metric_type="heart_rate",
                        value=hr_value,
                        timestamp=date.replace(hour=hour, minute=random.randint(0, 59)),
                        extra_data={"reading_type": "resting" if hour in [8, 20] else "active"}
                    ))

                # Generate sleep data
                sleep_variation = random.uniform(-1.5, 1.5)
                sleep_hours = max(4, base_sleep_hours + sleep_variation)

                # Sleep quality score (0-100)
                sleep_quality = random.randint(60, 95)

                session.add(HealthMetric(
                    user_id=user_id,
                    metric_type="sleep_duration",
                    value=sleep_hours,
                    timestamp=date.replace(hour=7, minute=0),
                    extra_data={"quality_score": sleep_quality, "bedtime": "22:30"}
                ))

                # Occasionally add other metrics
                if random.random() < 0.3:  # 30% chance
                    session.add(HealthMetric(
                        user_id=user_id,
                        metric_type="active_minutes",
                        value=random.randint(10, 90),
                        timestamp=date.replace(hour=19, minute=0),
                        extra_data={"activity_type": random.choice(["walking", "running", "cycling"])}
                    ))

            session.commit()
            print(f"✓ Generated {days_back} days of health metrics for user {user_id}")

        except Exception as e:
            session.rollback()
            print(f"✗ Error generating health metrics: {e}")
        finally:
            session.close()

    def generate_basic_conversation_history(self, user_id: int):
        """Generate basic conversation history"""
        session = self.db_manager.get_session()

        try:
            # Create a simple completed conversation
            past_conversation = Conversation(
                user_id=user_id,
                session_id=uuid.uuid4(),
                messages=[
                    {"role": "user", "content": "How did I sleep last night?", "timestamp": "2025-01-14T09:00:00Z"},
                    {"role": "assistant", "content": "You got 7.2 hours of sleep last night with a quality score of 78%. That's pretty good! You went to bed around 10:30 PM and had some restful deep sleep phases.", "timestamp": "2025-01-14T09:00:05Z"},
                    {"role": "user", "content": "What can I do to improve my sleep?", "timestamp": "2025-01-14T09:01:00Z"},
                    {"role": "assistant", "content": "Based on your data, I notice you sleep better on days when you get more steps. Try to get at least 8000 steps today, and consider doing some light stretching before bed.", "timestamp": "2025-01-14T09:01:08Z"}
                ],
                status="completed",
                ended_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            session.add(past_conversation)
            session.commit()

            print(f"✓ Generated basic conversation history for user {user_id}")
            print("  NOTE: Highlights will be generated by the highlights processor, not mock data")

        except Exception as e:
            session.rollback()
            print(f"✗ Error generating conversation history: {e}")
        finally:
            session.close()

    def generate_external_context(self):
        """Generate sample external context data"""
        session = self.db_manager.get_session()

        try:
            # Weather data for different locations
            weather_data = [
                {
                    "context_type": "weather",
                    "location": "Tel Aviv",
                    "data": {"temperature": 24, "condition": "sunny", "humidity": 65, "air_quality": "good"}
                },
                {
                    "context_type": "weather",
                    "location": "New York",
                    "data": {"temperature": 8, "condition": "cloudy", "humidity": 70, "air_quality": "moderate"}
                }
            ]

            for data in weather_data:
                context = ExternalContext(
                    context_type=data["context_type"],
                    location=data["location"],
                    data=data["data"]
                )
                session.add(context)

            session.commit()
            print("✓ Generated external context data")

        except Exception as e:
            session.rollback()
            print(f"✗ Error generating external context: {e}")
        finally:
            session.close()

    def generate_knowledge_base_samples(self):
        """Generate sample knowledge base entries"""
        session = self.db_manager.get_session()

        try:
            knowledge_entries = [
                {
                    "topic": "sleep_hygiene",
                    "content": "Maintaining consistent sleep and wake times helps regulate your circadian rhythm. Avoid screens 1 hour before bed and keep your bedroom cool and dark.",
                    "source": "Sleep Foundation Guidelines"
                },
                {
                    "topic": "step_goals",
                    "content": "The 10,000 steps per day goal is a good general target, but health benefits can be seen with as few as 7,000 steps daily for most adults.",
                    "source": "CDC Physical Activity Guidelines"
                },
                {
                    "topic": "heart_rate_zones",
                    "content": "Resting heart rate typically ranges from 60-100 bpm for adults. Athletes often have resting rates between 40-60 bpm due to improved cardiovascular fitness.",
                    "source": "American Heart Association"
                }
            ]

            for entry in knowledge_entries:
                kb = KnowledgeBase(
                    topic=entry["topic"],
                    content=entry["content"],
                    source=entry["source"]
                )
                session.add(kb)

            session.commit()
            print("✓ Generated knowledge base entries")

        except Exception as e:
            session.rollback()
            print(f"✗ Error generating knowledge base: {e}")
        finally:
            session.close()

    def generate_all_raw_data(self, num_users: int = 3, days_back: int = 14):
        """Generate complete set of RAW mock data only"""
        print("=== GENERATING RAW MOCK DATA ONLY ===")
        print("NOTE: Insights and highlights will be generated by their respective processors")

        # Create tables if they don't exist
        self.db_manager.create_tables()

        # Generate users and get their IDs
        user_ids = self.generate_sample_users(num_users)

        # Generate raw data for each user
        for user_id in user_ids:
            self.generate_health_metrics(user_id, days_back)
            self.generate_basic_conversation_history(user_id)

        # Generate external context
        self.generate_external_context()

        # Generate knowledge base
        self.generate_knowledge_base_samples()

        print("\n=== RAW MOCK DATA GENERATION COMPLETE ===")
        print("To generate insights: run the insights processor")
        print("To generate highlights: run the highlights processor")

        return user_ids

    def clean_database(self):
        """Clean all data from database (for fresh testing)"""
        session = self.db_manager.get_session()

        try:
            # Delete in correct order due to foreign key constraints
            from memory.database import Highlight, Insight, Conversation, HealthMetric, ExternalContext, KnowledgeBase, User

            session.query(Highlight).delete()
            session.query(Insight).delete()
            session.query(Conversation).delete()
            session.query(HealthMetric).delete()
            session.query(ExternalContext).delete()
            session.query(KnowledgeBase).delete()
            session.query(User).delete()

            session.commit()
            print("✓ Database cleaned")

        except Exception as e:
            session.rollback()
            print(f"✗ Error cleaning database: {e}")
        finally:
            session.close()


def main():
    """Generate raw mock data when run directly"""
    generator = MockDataGenerator()

    # Optionally clean database first
    # generator.clean_database()

    user_ids = generator.generate_all_raw_data(num_users=3, days_back=21)

    print(f"\nGenerated RAW data for {len(user_ids)} users with IDs: {user_ids}")
    print("Next steps:")
    print("1. Run insights processor: python -m memory.insights")
    print("2. Run highlights processor: python -m memory.highlights (when implemented)")
    print("3. Test the conversation system")


if __name__ == "__main__":
    main()