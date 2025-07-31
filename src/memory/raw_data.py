"""
Raw Data Loader - Fetches recent health metrics and user profile

This module loads the raw health data layer from the database, including:
- Steps, sleep, and heart rate metrics
- User demographic and preference information

"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from memory.database import HealthMetric, User, get_db_session

logger = logging.getLogger(__name__)

class RawDataLoader:
    def __init__(self, days_back: int = 7):
        self.days_back = days_back

    def load_user_data(self, user_id: int) -> Dict[str, Any]:
        session = get_db_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"[RawDataLoader] User {user_id} not found")
                return {}

            user_profile = {
                "age": user.age,
                "gender": user.gender,
                "location": user.location,
                "goals": user.goals or [],
                "preferences": user.preferences or {}
            }

            cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
            metrics = {}
            total_metrics = 0

            for metric in ["steps", "sleep_duration", "heart_rate"]:
                rows = session.query(HealthMetric).filter(
                    HealthMetric.user_id == user_id,
                    HealthMetric.metric_type == metric,
                    HealthMetric.timestamp >= cutoff
                ).order_by(HealthMetric.timestamp.desc()).limit(self.days_back).all()

                if rows:
                    key = metric.replace("_duration", "_hours")
                    values = [r.value for r in reversed(rows)]
                    metrics[key] = values
                    total_metrics += len(values)

            logger.info(f"[RawDataLoader] Loaded {total_metrics} metric points for user {user_id}")

            return {
                "user_profile": user_profile,
                "recent_metrics": metrics
            }

        except Exception as e:
            logger.error(f"[RawDataLoader] Failed to load raw data for user {user_id}: {e}", exc_info=True)
            return {}

        finally:
            session.close()
