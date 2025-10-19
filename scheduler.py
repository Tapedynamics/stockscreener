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

    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        # Schedule for Monday at 19:00 CET
        self.scheduler.add_job(
            func=self.run_rebalance,
            trigger=CronTrigger(
                day_of_week='mon',
                hour=19,
                minute=0,
                timezone=pytz.timezone('Europe/Rome')
            ),
            id='weekly_rebalance',
            name='Weekly Portfolio Rebalance',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("✅ Scheduler started - Weekly rebalance scheduled for Monday 19:00 CET")

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


def create_scheduler(screener_function):
    """
    Factory function to create and start a scheduler

    Args:
        screener_function: Function to call for rebalancing

    Returns:
        PortfolioScheduler instance
    """
    scheduler = PortfolioScheduler(screener_function)
    scheduler.start()
    return scheduler
