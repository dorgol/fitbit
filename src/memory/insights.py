"""
Insights Generation - Batch processing of health data into meaningful insights

Analyzes raw health metrics and generates insights that are stored in the database.
This runs as a batch job (daily) rather than real-time processing.
"""

import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
from sqlalchemy import and_
from sqlalchemy.orm import Session
import statistics
import logging

# Add src to path for imports
sys.path.append('src')

from memory.database import (
    DatabaseManager, User, HealthMetric, Insight
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InsightsGenerator:
    """Generates health insights from raw data using batch processing"""

    def __init__(self):
        self.db_manager = DatabaseManager()

    def generate_insights_for_user(self, user_id: int, lookback_days: int = 30) -> List[Dict]:
        """
        Generate all insights for a single user

        Args:
            user_id: User to generate insights for
            lookback_days: How many days of data to analyze

        Returns:
            List of insight dictionaries ready for database storage
        """
        session = self.db_manager.get_session()
        insights = []

        try:
            # Get user profile for context
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found")
                return insights

            # Generate different types of insights
            insights.extend(self._analyze_step_trends(session, user_id, lookback_days))
            insights.extend(self._analyze_sleep_patterns(session, user_id, lookback_days))
            insights.extend(self._analyze_heart_rate_trends(session, user_id, lookback_days))
            insights.extend(self._analyze_goal_progress(session, user_id, user.goals, lookback_days))
            insights.extend(self._detect_correlations(session, user_id, lookback_days))
            insights.extend(self._detect_anomalies(session, user_id, lookback_days))

            logger.info(f"Generated {len(insights)} insights for user {user_id}")

        except Exception as e:
            logger.error(f"Error generating insights for user {user_id}: {e}")
        finally:
            session.close()

        return insights

    @staticmethod
    def _get_metric_values(session: Session, user_id: int, metric_type: str,
                          days_back: int) -> List[Tuple[datetime, float]]:
        """Get metric values with timestamps for analysis"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        metrics = session.query(HealthMetric).filter(
            and_(
                HealthMetric.user_id == user_id,
                HealthMetric.metric_type == metric_type,
                HealthMetric.timestamp >= cutoff_date
            )
        ).order_by(HealthMetric.timestamp.desc()).all()

        return [(metric.timestamp, metric.value) for metric in metrics]

    def _analyze_step_trends(self, session: Session, user_id: int, days_back: int) -> List[Dict]:
        """Analyze step count trends and patterns"""
        insights = []

        step_data = self._get_metric_values(session, user_id, "steps", days_back)
        if len(step_data) < 7:  # Need at least a week of data
            return insights

        # Extract just the values for statistical analysis
        recent_values = [value for _, value in step_data[:14]]  # Last 2 weeks
        older_values = [value for _, value in step_data[14:28]]  # Previous 2 weeks

        if len(recent_values) >= 7 and len(older_values) >= 7:
            recent_avg = statistics.mean(recent_values)
            older_avg = statistics.mean(older_values)
            change_percent = ((recent_avg - older_avg) / older_avg) * 100

            if abs(change_percent) > 10:  # Significant change
                trend_direction = "increased" if change_percent > 0 else "decreased"
                insights.append({
                    "category": "trend",
                    "finding": f"Your average daily steps have {trend_direction} by {abs(change_percent):.0f}% over the past two weeks",
                    "timeframe": "2_weeks",
                    "confidence": min(0.95, abs(change_percent) / 100 + 0.6),
                    "extra_data": {
                        "recent_avg": recent_avg,
                        "older_avg": older_avg,
                        "change_percent": change_percent,
                        "metric_type": "steps"
                    }
                })

        # Weekend vs weekday analysis
        weekday_steps = []
        weekend_steps = []

        for timestamp, value in step_data[:21]:  # Last 3 weeks
            if timestamp.weekday() < 5:  # Monday = 0, Sunday = 6
                weekday_steps.append(value)
            else:
                weekend_steps.append(value)

        if len(weekday_steps) >= 5 and len(weekend_steps) >= 2:
            weekday_avg = statistics.mean(weekday_steps)
            weekend_avg = statistics.mean(weekend_steps)
            difference_percent = ((weekday_avg - weekend_avg) / weekend_avg) * 100

            if abs(difference_percent) > 20:
                pattern_type = "more active on weekdays" if difference_percent > 0 else "more active on weekends"
                insights.append({
                    "category": "pattern",
                    "finding": f"You're consistently {pattern_type}, with {abs(difference_percent):.0f}% difference in average steps",
                    "timeframe": "3_weeks",
                    "confidence": 0.8,
                    "extra_data": {
                        "weekday_avg": weekday_avg,
                        "weekend_avg": weekend_avg,
                        "difference_percent": difference_percent,
                        "metric_type": "steps"
                    }
                })

        return insights

    def _analyze_sleep_patterns(self, session: Session, user_id: int, days_back: int) -> List[Dict]:
        """Analyze sleep duration and quality patterns"""
        insights = []

        sleep_data = self._get_metric_values(session, user_id, "sleep_duration", days_back)
        if len(sleep_data) < 7:
            return insights

        values = [value for _, value in sleep_data[:14]]  # Last 2 weeks
        avg_sleep = statistics.mean(values)

        # Sleep duration assessment
        if avg_sleep < 6.5:
            insights.append({
                "category": "health_concern",
                "finding": f"Your average sleep of {avg_sleep:.1f} hours is below the recommended 7-9 hours",
                "timeframe": "2_weeks",
                "confidence": 0.9,
                "extra_data": {
                    "avg_sleep": avg_sleep,
                    "recommendation": "aim_for_7_hours",
                    "metric_type": "sleep_duration"
                }
            })
        elif avg_sleep > 9:
            insights.append({
                "category": "observation",
                "finding": f"You're getting {avg_sleep:.1f} hours of sleep on average, which is above typical recommendations",
                "timeframe": "2_weeks",
                "confidence": 0.8,
                "extra_data": {
                    "avg_sleep": avg_sleep,
                    "metric_type": "sleep_duration"
                }
            })

        # Sleep consistency
        if len(values) >= 7:
            sleep_stdev = statistics.stdev(values)
            if sleep_stdev < 0.5:
                insights.append({
                    "category": "positive_pattern",
                    "finding": "Your sleep schedule is very consistent, which is great for your circadian rhythm",
                    "timeframe": "2_weeks",
                    "confidence": 0.85,
                    "extra_data": {
                        "sleep_consistency": sleep_stdev,
                        "metric_type": "sleep_duration"
                    }
                })
            elif sleep_stdev > 1.5:
                insights.append({
                    "category": "improvement_opportunity",
                    "finding": "Your sleep duration varies significantly. Try to maintain a more consistent bedtime",
                    "timeframe": "2_weeks",
                    "confidence": 0.75,
                    "extra_data": {
                        "sleep_consistency": sleep_stdev,
                        "metric_type": "sleep_duration"
                    }
                })

        return insights

    @staticmethod
    def _analyze_heart_rate_trends(session: Session, user_id: int, days_back: int) -> List[Dict]:
        """Analyze resting heart rate trends"""
        insights = []

        # Get only resting heart rate readings
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        hr_metrics = session.query(HealthMetric).filter(
            and_(
                HealthMetric.user_id == user_id,
                HealthMetric.metric_type == "heart_rate",
                HealthMetric.timestamp >= cutoff_date,
                HealthMetric.extra_data.op('->>')('reading_type') == 'resting'
            )
        ).order_by(HealthMetric.timestamp.desc()).all()

        if len(hr_metrics) < 10:
            return insights

        # Analyze trend over time
        recent_hrs = [metric.value for metric in hr_metrics[:14]]  # Last 2 weeks
        older_hrs = [metric.value for metric in hr_metrics[14:28]]  # Previous 2 weeks

        if len(recent_hrs) >= 7 and len(older_hrs) >= 7:
            recent_avg = statistics.mean(recent_hrs)
            older_avg = statistics.mean(older_hrs)
            change = recent_avg - older_avg

            if abs(change) > 3:  # Significant change in resting HR
                trend_direction = "decreased" if change < 0 else "increased"
                health_implication = "improved cardiovascular fitness" if change < 0 else "check if you're getting enough rest"

                insights.append({
                    "category": "trend",
                    "finding": f"Your resting heart rate has {trend_direction} by {abs(change):.1f} bpm, suggesting {health_implication}",
                    "timeframe": "2_weeks",
                    "confidence": 0.8,
                    "extra_data": {
                        "recent_avg_hr": recent_avg,
                        "older_avg_hr": older_avg,
                        "change_bpm": change,
                        "metric_type": "heart_rate"
                    }
                })

        return insights

    def _analyze_goal_progress(self, session: Session, user_id: int, goals: List[str], days_back: int) -> List[Dict]:
        """Analyze progress toward user's stated goals"""
        insights = []

        if not goals:
            return insights

        # Check step goals
        if "10k_steps_daily" in goals:
            step_data = self._get_metric_values(session, user_id, "steps", 7)  # Last week
            if step_data:
                values = [value for _, value in step_data]
                days_over_10k = sum(1 for value in values if value >= 10000)
                total_days = len(values)

                if total_days >= 5:
                    percentage = (days_over_10k / total_days) * 100
                    insights.append({
                        "category": "goal_progress",
                        "finding": f"You hit your 10k steps goal {days_over_10k} out of {total_days} days this week ({percentage:.0f}%)",
                        "timeframe": "1_week",
                        "confidence": 0.95,
                        "extra_data": {
                            "goal": "10k_steps_daily",
                            "days_achieved": days_over_10k,
                            "total_days": total_days,
                            "percentage": percentage
                        }
                    })

        # Check sleep goals
        if "better_sleep" in goals:
            sleep_data = self._get_metric_values(session, user_id, "sleep_duration", 14)
            if sleep_data:
                values = [value for _, value in sleep_data]
                avg_sleep = statistics.mean(values)
                good_sleep_days = sum(1 for value in values if 7 <= value <= 9)

                insights.append({
                    "category": "goal_progress",
                    "finding": f"You're averaging {avg_sleep:.1f} hours of sleep, with {good_sleep_days} days in the optimal 7-9 hour range",
                    "timeframe": "2_weeks",
                    "confidence": 0.9,
                    "extra_data": {
                        "goal": "better_sleep",
                        "avg_sleep": avg_sleep,
                        "optimal_days": good_sleep_days,
                        "total_days": len(values)
                    }
                })

        return insights

    @staticmethod
    def _detect_correlations(session: Session, user_id: int, days_back: int) -> List[Dict]:
        """Detect correlations between different metrics"""
        insights = []

        # Get overlapping data for steps and sleep
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Group metrics by date for correlation analysis
        daily_data = {}

        metrics = session.query(HealthMetric).filter(
            and_(
                HealthMetric.user_id == user_id,
                HealthMetric.metric_type.in_(["steps", "sleep_duration"]),
                HealthMetric.timestamp >= cutoff_date
            )
        ).all()

        for metric in metrics:
            date_key = metric.timestamp.date()
            if date_key not in daily_data:
                daily_data[date_key] = {}
            daily_data[date_key][metric.metric_type] = metric.value

        # Find days with both steps and sleep data
        complete_days = {date: data for date, data in daily_data.items()
                        if "steps" in data and "sleep_duration" in data}

        if len(complete_days) >= 10:
            steps_values = [data["steps"] for data in complete_days.values()]
            sleep_values = [data["sleep_duration"] for data in complete_days.values()]

            # Simple correlation analysis (high steps -> better sleep)
            high_step_days = [(steps, sleep) for steps, sleep in zip(steps_values, sleep_values)
                             if steps > statistics.mean(steps_values)]
            low_step_days = [(steps, sleep) for steps, sleep in zip(steps_values, sleep_values)
                            if steps < statistics.mean(steps_values)]

            if len(high_step_days) >= 3 and len(low_step_days) >= 3:
                high_step_sleep = statistics.mean([sleep for _, sleep in high_step_days])
                low_step_sleep = statistics.mean([sleep for _, sleep in low_step_days])

                if high_step_sleep > low_step_sleep + 0.3:  # At least 18 minutes difference
                    insights.append({
                        "category": "correlation",
                        "finding": f"You tend to sleep {(high_step_sleep - low_step_sleep) * 60:.0f} minutes longer on days with higher step counts",
                        "timeframe": f"{days_back}_days",
                        "confidence": 0.7,
                        "extra_data": {
                            "correlation": "steps_sleep_positive",
                            "high_step_sleep": high_step_sleep,
                            "low_step_sleep": low_step_sleep,
                            "sample_size": len(complete_days)
                        }
                    })

        return insights

    def _detect_anomalies(self, session: Session, user_id: int, days_back: int) -> List[Dict]:
        """Detect unusual readings or patterns"""
        insights = []

        # Check for unusually high/low values in recent days
        for metric_type in ["steps", "sleep_duration", "heart_rate"]:
            data = self._get_metric_values(session, user_id, metric_type, days_back)

            if len(data) < 10:
                continue

            recent_values = [value for _, value in data[:7]]  # Last week
            baseline_values = [value for _, value in data[7:]]  # Previous data

            if len(baseline_values) >= 10:
                baseline_mean = statistics.mean(baseline_values)
                baseline_stdev = statistics.stdev(baseline_values)

                # Check recent values for anomalies
                for timestamp, value in data[:3]:  # Last 3 days
                    z_score = abs(value - baseline_mean) / baseline_stdev if baseline_stdev > 0 else 0

                    if z_score > 2:  # More than 2 standard deviations
                        direction = "unusually high" if value > baseline_mean else "unusually low"

                        # Fix timezone-aware datetime comparison
                        now = datetime.now(timezone.utc)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        days_ago = (now - timestamp).days

                        insights.append({
                            "category": "anomaly",
                            "finding": f"Your {metric_type.replace('_', ' ')} was {direction} {days_ago} days ago ({value:.1f} vs typical {baseline_mean:.1f})",
                            "timeframe": "recent",
                            "confidence": min(0.9, z_score / 3),
                            "extra_data": {
                                "metric_type": metric_type,
                                "anomaly_value": value,
                                "baseline_mean": baseline_mean,
                                "z_score": z_score,
                                "days_ago": days_ago
                            }
                        })

        return insights

    def store_insights(self, user_id: int, insights: List[Dict]) -> int:
        """Store generated insights in the database"""
        session = self.db_manager.get_session()
        stored_count = 0

        try:
            # Clear old insights for this user (older than 7 days)
            old_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            session.query(Insight).filter(
                and_(
                    Insight.user_id == user_id,
                    Insight.generated_at < old_cutoff
                )
            ).delete()

            # Store new insights
            for insight_data in insights:
                insight = Insight(
                    user_id=user_id,
                    category=insight_data["category"],
                    finding=insight_data["finding"],
                    timeframe=insight_data["timeframe"],
                    confidence=insight_data["confidence"],
                    extra_data=insight_data.get("extra_data", {}),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7)
                )
                session.add(insight)
                stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} insights for user {user_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing insights for user {user_id}: {e}")
            raise
        finally:
            session.close()

        return stored_count



def process_all_users(lookback_days: int = 30) -> Dict[str, int]:
    """
    Process insights for all users (main batch job function)

    Args:
        lookback_days: How far back to look when analyzing health data

    Returns:
        A summary dictionary with counts of processed users, insights, and errors
    """
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    generator = InsightsGenerator()

    results = {"processed": 0, "insights_generated": 0, "errors": 0}

    try:
        users = session.query(User).all()

        for user in users:
            try:
                insights = generator.generate_insights_for_user(user.id, lookback_days)
                stored = generator.store_insights(user.id, insights)

                results["processed"] += 1
                results["insights_generated"] += stored

                logger.info(f"Processed user {user.id}: {stored} insights generated")

            except Exception as e:
                logger.error(f"Error processing user {user.id}: {e}", exc_info=True)
                results["errors"] += 1

    finally:
        session.close()

    logger.info(f"Batch processing complete: {results}")
    return results


def run_daily_insights_batch():
    """
    Main function to run the daily insights batch job
    """
    logger.info("Starting daily insights batch processing...")

    results = process_all_users(lookback_days=30)

    logger.info(f"Daily insights batch complete: {results}")
    return results


if __name__ == "__main__":
    # Run the batch job
    run_daily_insights_batch()
