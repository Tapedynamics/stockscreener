#!/usr/bin/env python3
"""
Scheduler for automated portfolio rebalancing
Runs every Monday at 19:00 CET
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioScheduler:
    def __init__(self, screener_function):
        """
        Initialize scheduler with screener function

        Args:
            screener_function: Function to call for rebalancing
        """
        self.screener_function = screener_function
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Rome'))
        self.is_running = False

    def start(self, run_today_at_19=False):
        """Start the scheduler

        Args:
            run_today_at_19: If True, adds one-time job for today at 19:00
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        # Schedule recurring Monday at 20:00 CET (19:00 London)
        self.scheduler.add_job(
            func=self.run_rebalance,
            trigger=CronTrigger(
                day_of_week='mon',
                hour=20,
                minute=0,
                timezone=pytz.timezone('Europe/Rome')
            ),
            id='weekly_rebalance',
            name='Weekly Portfolio Rebalance',
            replace_existing=True
        )

        # Add one-time job for today at 20:00 if requested
        if run_today_at_19:
            from datetime import datetime
            tz = pytz.timezone('Europe/Rome')
            now = datetime.now(tz)
            today_20 = now.replace(hour=20, minute=0, second=0, microsecond=0)

            if now < today_20:  # Only if 20:00 hasn't passed
                self.scheduler.add_job(
                    func=self.run_rebalance,
                    trigger='date',
                    run_date=today_20,
                    id='first_order_today',
                    name='First Order - Today 20:00 CET',
                    replace_existing=True
                )
                logger.info(f"🎯 FIRST ORDER scheduled for TODAY at 20:00 CET / 19:00 London (in {int((today_20 - now).total_seconds() / 60)} minutes)")
            else:
                logger.warning("20:00 CET has already passed today - first order skipped")

        self.scheduler.start()
        self.is_running = True

        logger.info("✅ Scheduler started - Weekly rebalance scheduled for Monday 20:00 CET (19:00 London)")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("⏹️ Scheduler stopped")

    def run_rebalance(self):
        """
        Execute the rebalancing job
        This is called automatically every Monday at 19:00
        """
        try:
            logger.info("🤖 AI Agent: Starting automated weekly rebalance...")

            # Call the screener function
            result = self.screener_function()

            if result.get('success'):
                logger.info(f"✅ Rebalance completed successfully - {result.get('total_stocks', 0)} stocks in portfolio")
            else:
                logger.error(f"❌ Rebalance failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"❌ Error during automated rebalance: {str(e)}")

    def get_next_run_time(self):
        """Get the next scheduled run time"""
        job = self.scheduler.get_job('weekly_rebalance')
        if job:
            return job.next_run_time
        return None

    def get_status(self):
        """Get scheduler status"""
        next_run = self.get_next_run_time()

        return {
            'running': self.is_running,
            'next_run': next_run.isoformat() if next_run else None,
            'timezone': 'Europe/Rome'
        }


def create_scheduler(screener_function, run_today_at_19=False):
    """
    Factory function to create and start a scheduler

    Args:
        screener_function: Function to call for rebalancing
        run_today_at_19: If True, schedule first order today at 19:00

    Returns:
        PortfolioScheduler instance
    """
    scheduler = PortfolioScheduler(screener_function)
    scheduler.start(run_today_at_19=run_today_at_19)
    return scheduler
